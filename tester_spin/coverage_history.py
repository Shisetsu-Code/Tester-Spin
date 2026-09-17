"""Keep unresolved, explicitly announced branches across short audit runs."""
from __future__ import annotations

import copy
import json
import threading
from pathlib import Path

_lock = threading.RLock()


def retain_pending_branches(directory, result):
    if directory is None:
        return
    root = Path(directory)
    path = root / 'coverage-history.json'

    def absorb(pending, modes, source):
        for mode in modes:
            if not isinstance(mode, dict) or mode.get('coverage_required') is not True:
                continue
            key = str(mode.get('id') or '')
            if not key:
                continue
            prior = pending.get(key, {})
            required = {str(x) for x in mode.get('required_options', [])}
            covered = {str(x) for x in mode.get('covered_options', [])}
            old = set(prior.get('required_options', []))
            if required and 'DOMAIN_UNRESOLVED' not in required:
                old.discard('DOMAIN_UNRESOLVED')
            target = max(1, int(prior.get('required_samples') or 1), int(mode.get('required_samples') or 1))
            counts = mode.get('sample_counts')
            missing = (old | required) - covered
            if isinstance(counts, dict):
                missing |= {option for option in old | required if int(counts.get(option, 0)) < target}
            elif target > 1:
                missing |= old | required
            if not missing:
                pending.pop(key, None)
                continue
            item = copy.deepcopy(mode)
            item.update(required_options=sorted(missing), covered_options=[],
                        required_samples=target,
                        historical_source=prior.get('historical_source') or source)
            pending[key] = item

    with _lock:
        pending = {}
        if path.exists():
            saved = json.loads(path.read_text(encoding='utf-8'))
            if saved.get('provider') != result.provider or saved.get('slug') != result.slug:
                raise ValueError('Historial de cobertura pertenece a otro juego')
            pending = saved['pending']
        else:
            # One-time migration; never mistake other games or arbitrary JSON for history.
            files = sorted((root/'tests').glob('*/result.json'), key=lambda p:p.stat().st_mtime_ns)
            for previous in files:
                if result.run_dir and previous.parent.resolve() == Path(result.run_dir).resolve():
                    continue
                try:
                    record = json.loads(previous.read_text(encoding='utf-8'))
                except (OSError, ValueError):
                    continue
                if record.get('provider') == result.provider and record.get('slug') == result.slug:
                    absorb(pending, record.get('discovered_modes', []), str(previous))
        absorb(pending, result.discovered_modes, result.run_dir)
        current = {str(m.get('id')):m for m in result.discovered_modes if isinstance(m, dict)}
        for key, item in pending.items():
            if key in current:
                mode = current[key]
                mode['coverage_required'] = True
                mode.setdefault('branch_signature', item.get('branch_signature', key))
                mode['required_samples'] = max(int(mode.get('required_samples') or 1), int(item.get('required_samples') or 1))
                mode['required_options'] = sorted(set(map(str, mode.get('required_options', []))) | set(item['required_options']))
                mode['historical_source'] = item['historical_source']
            else:
                inherited = copy.deepcopy(item)
                inherited.update(observed=False, historical_pending=True)
                inherited['reason'] = 'Pendiente de una corrida anterior; no se volvió a demostrar su cobertura.'
                result.discovered_modes.append(inherited)
        root.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps({'schema':'tester-spin/coverage-history/v1',
            'provider':result.provider,'slug':result.slug,'pending':pending},ensure_ascii=False,indent=2),encoding='utf-8')
        temporary.replace(path)
