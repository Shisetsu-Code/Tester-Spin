"""Inspect ONLY public game source for an explicit ChooseFG pick serializer.

No wagers or request replays. Limited fragments; no session URLs, auth headers,
cookies, full JS, or socket payloads are ever printed or committed.
"""
import json,re,threading
from pathlib import Path
from tempfile import TemporaryDirectory
from tester_spin.providers.playtech.direct_runtime import DemoSession
from tester_spin.providers.playtech.client_sources import _function_bodies

TERMS=('ChooseFG','pick','playOut','48775','parameters','selection')
def safe(s):
    s=re.sub(r'https?://[^\s;\"\']+','[URL]',s)
    s=re.sub(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}','[ID]',s,re.I)
    s=re.sub(r'[A-Za-z0-9+/=]{64,}','[OPAQUE]',s)
    return s.replace('\n',' ')[:340]

with TemporaryDirectory() as td:
    with DemoSession('gpas_sorome_pop',Path(td),25,threading.Event()) as session:
        scripts=[s for s in session.sources if isinstance(s,str)]
        found=[]
        for index,s in enumerate(scripts):
            for term in TERMS:
                for match in list(re.finditer(re.escape(term),s,re.I))[:5]:
                    frag=s[max(0,match.start()-120):match.end()+200]
                    found.append({'source':index,'term':term,'snippet':safe(frag)})
        functions={}
        for source in scripts:
            for name,(args,body) in _function_bodies(source).items():
                hits=sorted({term for term in TERMS if term.lower() in body.lower()})
                if ('pick' in hits or 'ChooseFG' in hits) and len(body)<4000:
                    functions[name]={'argc':len(args),'terms':hits,
                                     'snippet':safe(body[:330])}
        print('LEGACY_CHOICE_SOURCE',json.dumps({
            'code':'gpas_sorome_pop',
            'script_count':len(scripts),
            'hits':found[:22],
            'functions':dict(list(functions.items())[:18])},ensure_ascii=False))
