"""Annotate certified bonus picks without equating one choice with all coverage."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from tester_spin.providers.pragmatic_protocol import server_error
from tester_spin.providers.pragmatic_preparation_coverage import selection_artifacts

_ORIGIN = 'pragmatic_bonus_selection_artifacts'


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _integer(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def annotate_bonus_coverage(result):
    """Refresh per-mode/state/source coverage from attempts and their base probes.

    A sample is an independent terminal attempt with two confirmed base cycles,
    not another pick or probe in the same attempt. Linked bootstrap observations add SPIN obligations but never count as samples.
    A later verified SPIN with the same contract and state can satisfy them.
    """
    groups = {}
    target = max(1, _integer(getattr(result, 'samples_per_path', 1), 1))
    for attempt in result.attempts:
        if not attempt.artifact_dir:
            continue
        directory = Path(attempt.artifact_dir)
        proof = _read(directory / 'return-to-base.json')
        valid_attempt = (attempt.ok and attempt.terminal and proof.get('status') == 'CONFIRMED'
                         and _integer(proof.get('consecutive_base')) >= 2)
        accepted = defaultdict(set)
        for path, origin_mode, phase in selection_artifacts(attempt, result, 'step-*.bonus-selection.json', recursive_attempt=True):
            record = _read(path)
            raw_domain = record.get('domain')
            if not isinstance(raw_domain, list) or not raw_domain:
                continue
            domain = {str(value) for value in raw_domain}
            if any(not value.isdecimal() for value in domain):
                continue
            signature = str(record.get('branch_signature') or '')
            source_hash = str(record.get('contract_sha256') or '')
            key = (origin_mode, signature, source_hash)
            group = groups.setdefault(key, {'required': set(), 'counts': defaultdict(int), 'record': record, 'source_phases': set()})
            group['source_phases'].add(phase)
            group['required'].update(domain)
            selected = str(record.get('selected'))
            response = _read(path.with_name(path.name.replace('.bonus-selection.json', '.response.json')))
            http = _read(path.with_name(path.name.replace('.bonus-selection.json', '.http.json')))
            valid_response = bool(response) and not server_error(response) and _integer(http.get('status'), 200) < 400
            if phase == 'attempt' and valid_attempt and valid_response and signature and source_hash and selected in domain:
                accepted[key].add(selected)
        for key, choices in accepted.items():
            for selected in choices:
                groups[key]['counts'][selected] += 1

    result.discovered_modes = [row for row in result.discovered_modes if row.get('coverage_origin') != _ORIGIN]
    pending = False
    for (mode_id, signature, source_hash), group in sorted(groups.items()):
        required = sorted(group['required'], key=int)
        counts = dict(sorted(group['counts'].items(), key=lambda pair: int(pair[0])))
        covered = [option for option in required if counts.get(option, 0) >= target]
        pending = pending or len(covered) < len(required)
        identity = hashlib.sha256(json.dumps([mode_id, signature, source_hash]).encode('utf-8')).hexdigest()[:16]
        record = group['record']
        result.discovered_modes.append({
            'id': f'{mode_id}_BONUS_PICK_{identity}', 'kind': 'CHOICE_BRANCH',
            'origin_mode_id': mode_id, 'coverage_origin': _ORIGIN, 'source_phases': sorted(group['source_phases']),
            'observed': True, 'executable': bool(signature and source_hash), 'coverage_required': True,
            'branch_signature': f'{mode_id}:{signature}:{source_hash}',
            'contract_branch_signature': signature,
            'required_options': required, 'covered_options': covered,
            'required_samples': target, 'sample_counts': counts,
            'contract_source': record.get('contract_source', ''), 'contract_sha256': source_hash,
            'reason': 'Cada elección de bonus exige respuesta válida, ronda terminal y dos ciclos base confirmados; muestras por intento independiente.',
        })
    if pending and result.status == 'OK':
        result.status = 'PARCIAL'
    return result
