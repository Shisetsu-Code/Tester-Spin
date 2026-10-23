"""Export sanitized local-demo events and independently public client sources."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import requests
from tester_spin.run_result_publisher import _public_value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--games', nargs='+', required=True)
    args = parser.parse_args()
    root = args.data_root.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {'schema': 'tester-spin/playtech-partial-evidence/v1', 'runs': []}
    for code in args.games:
        runs = sorted((root/'providers/playtech'/('game-'+code)/'analysis/runs').glob('*'))
        if not runs:
            report['runs'].append({'game': code, 'error': 'NO_RUN'})
            continue
        run = runs[-1].resolve()
        run.relative_to(root)
        target = args.output_dir/code
        target.mkdir(exist_ok=True)
        row = {'game': code, 'run': run.name, 'events': [], 'resources': [], 'skipped': []}
        for source in sorted(run.rglob('*')):
            if not source.is_file() or source.suffix not in {'.json', '.jsonl'}:
                continue
            relative = source.relative_to(run)
            if any(part.startswith('.') or 'private' in part.lower() for part in relative.parts):
                continue
            if source.stat().st_size > 16*1024*1024:
                row['skipped'].append(str(relative))
                continue
            destination = target/relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.suffix == '.jsonl':
                records = [_public_value(json.loads(line)) for line in source.read_text().splitlines() if line.strip()]
                destination.write_text(''.join(json.dumps(item, ensure_ascii=False)+'\n' for item in records))
            else:
                destination.write_text(json.dumps(_public_value(json.loads(source.read_text())), indent=2, ensure_ascii=False)+'\n')
            row['events'].append(str(relative))
        har = run/'session.har'
        if har.is_file() and har.stat().st_size <= 200*1024*1024:
            entries = json.loads(har.read_text()).get('log', {}).get('entries', [])
            seen = set()
            for entry in entries:
                url = urlsplit(entry.get('request', {}).get('url', ''))
                if url.scheme != 'https' or url.hostname != 'cachedownload.playtechone.com' or '/'+code+'/' not in url.path:
                    continue
                if not (url.path.endswith('.cache.js') or url.path.endswith('.jmm')):
                    continue
                public_url = urlunsplit((url.scheme, url.netloc, url.path, '', ''))
                if public_url in seen:
                    continue
                seen.add(public_url)
                content = entry.get('response', {}).get('content', {})
                text = content.get('text')
                if not isinstance(text, str):
                    continue
                captured = base64.b64decode(text, validate=True) if content.get('encoding') == 'base64' else text.encode()
                try:
                    response = requests.get(public_url, timeout=30, allow_redirects=False)
                    response.raise_for_status()
                    if response.status_code != 200 or len(response.content) > 16*1024*1024 or response.content != captured:
                        raise ValueError('PUBLIC_SOURCE_DIFFERS_FROM_CAPTURE')
                    digest = hashlib.sha256(captured).hexdigest()
                    relative = Path('public-client')/(digest+('.jmm' if url.path.endswith('.jmm') else '.js'))
                    (target/relative).parent.mkdir(exist_ok=True)
                    (target/relative).write_bytes(captured)
                    row['resources'].append({'url': public_url, 'sha256': digest, 'bytes': len(captured), 'path': str(relative)})
                except Exception as exc:
                    row['skipped'].append({'url': public_url, 'reason': type(exc).__name__+': '+str(exc)})
        report['runs'].append(row)
    (args.output_dir/'capture-index.json').write_text(json.dumps(_public_value(report), indent=2)+'\n')
    print(json.dumps({row['game']: {'resources': len(row.get('resources', [])), 'event_files': len(row.get('events', []))} for row in report['runs']}))


if __name__ == '__main__':
    main()
