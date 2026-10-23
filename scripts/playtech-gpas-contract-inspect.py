"""Inspect only public/current GPAS contract evidence; no wager is sent."""
import argparse
import json
import re
import threading
from tempfile import TemporaryDirectory
from pathlib import Path
from tester_spin.providers.playtech.direct_runtime import DemoSession
from tester_spin.providers.playtech.protocol import resolve_configuration
from tester_spin.providers.playtech.primitives import client_contract
from tester_spin.providers.playtech.client_sources import compiled_pick_binding

def inspect(code):
    with TemporaryDirectory() as temp:
        with DemoSession(code,Path(temp),15,threading.Event()) as session:
            contract=client_contract(session.manifest,session.sources,adapter_config=session.adapter_config)
            current=resolve_configuration(session.config,{"betType":"default"})
            game=current.get("game",{})
            costs=game.get("costConfiguration",[])
            text="\n".join(session.sources)
            def row(x):
                params=x.get("parameters") if isinstance(x.get("parameters"),dict) else {}
                scope=game.get("namedScopes",{}).get(x.get("name"),{})
                return dict(name=x.get("name"),cost=x.get("cost"),
                    starting_mode=params.get("startingMode"),starting_plays=params.get("startingPlays"),
                    winline=params.get("winline"),scope=scope)
            return dict(code=code,rows=[row(x) for x in costs if isinstance(x,dict)][:40],
                current_active_options=game.get("activeBetOptions"),
                feature_bet_enabled=game.get("featureBetEnabled"),extra_bet_enabled=game.get("extraBetEnabled"),
                dialect=contract.get("dialect"),standard_start_bound=contract.get("standard_start_bound"),
                base_selector=contract.get("base_selector"),pick_bound=contract.get("pick_bound"),
                signals=dict(extra_controller=bool(re.search(r"ExtraBets?(?:Module|Controller|Configuration|Widget)",text)),
                    purchase_controller=bool(re.search(r"BuyFeature(?:Module|Controller|Configuration)",text)),
                    has_literal_pick=bool(re.search(r"[\"\']pick[\"\']",text)),
                    has_pick_controller="FGPickController" in text,
                    has_play_out="GLU.game.playOut" in text,
                    compiled_pick_binding=compiled_pick_binding(text),
                    known_stake_cost="stakeCostUuid" in text,
                    known_feature_type="featureType" in text),
                adapter_map_keys=sorted(contract.get("adapter_maps",{})))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("codes",nargs="+")
    args=ap.parse_args()
    for code in args.codes:
        try: result=inspect(code)
        except Exception as e: result=dict(code=code,error=type(e).__name__+":"+str(e)[:150])
        print("GPAS_CONTRACT_EVIDENCE "+json.dumps(result,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
