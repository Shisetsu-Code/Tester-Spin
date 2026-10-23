"""Read public Playtech GPAS release keys without executing games or wagers."""
from __future__ import annotations

import argparse
import json
import re
import requests

ROOT = 'https://gpas-games.playtechone.com/'


def candidates(code: str, keys):
    """Inspect only bounded catalog aliases; never guess a runnable identity."""
    if not re.fullmatch(r'gpas_[A-Za-z0-9_]+', code):
        raise ValueError('UNSUPPORTED_GAME_CODE')
    term = code.removeprefix('gpas_')
    alternatives = {code.lower(), term.lower(), term.removesuffix('_pop').lower()}
    exact = code in keys
    similar = sorted(k for k in keys if isinstance(k, str) and
                     any(x and x in k.lower() for x in alternatives))
    return dict(code=code, exact=exact, matching_keys=similar[:12],
                candidate_count=len(similar))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('codes', nargs='+')
    args=parser.parse_args()
    with requests.Session() as s:
        def read(path):
            r=s.get(ROOT+path,timeout=15,allow_redirects=False)
            r.raise_for_status()
            if r.is_redirect or len(r.content)>8*1024*1024:
                raise ValueError('RELEASE_RESPONSE_INVALID')
            return r.json()
        release=read('gpasclientconf_live.php')['id']
        if not isinstance(release,str) or not re.fullmatch(r'[0-9.]+',release):
            raise ValueError('RELEASE_ID_INVALID')
        bundle=read(release+'/logical_bundle.php')
    mapping=bundle.get('games')
    if not isinstance(mapping,dict):
        raise ValueError('RELEASE_GAMES_MISSING')
    print(json.dumps(dict(release=release,declared_games=len(mapping),
                          results=[candidates(code,mapping) for code in args.codes]),
                     ensure_ascii=False))
if __name__=='__main__':
    main()
