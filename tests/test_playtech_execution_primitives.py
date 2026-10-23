import base64, json, zlib
import unittest
from tester_spin.providers.playtech.primitives import (decode_game_data, client_contract, discover_modes, entry_command, PickState, RoundLedger)

CLASS = "com.pt.gpas.platform.game.OgwCorosinGameCommand"
SOURCE = 'GLU.game.playMoney(x,y,z); GLU.game.playOut(x,y); ID:40021; ID:48775; "'+CLASS+'"; BuyFeatureModule ExtraBetsModule function f(){var m={};m["pick"]=value;}'

def cfg(costs=None):
 return {"game":{"baseCostMultipliers":[1,2],"costConfiguration": costs or [{"uuid":"base-id","name":"Default","cost":10,"parameters":{"startingMode":"base-uuid"}}]}}
def contract(legacy=False):
 return client_contract({"setup":{"usesLegacyBetApi":legacy}},[SOURCE + (' GLU.game.bet(x,y); GLU.game.send(x,y); stakeCostUuid:x' if legacy else '')])

class ExecutionPrimitivesTests(unittest.TestCase):
 def test_decode_packed_and_reject_truncated_or_bomb(self):
  raw=json.dumps({"nextRound":"pick"}).encode();packed={"_type":"gpas:packed:zlib","payload":base64.b64encode(zlib.compress(raw)).decode()}
  self.assertEqual(decode_game_data(packed),{"nextRound":"pick"})
  with self.assertRaises(ValueError):decode_game_data({"_type":"gpas:packed:zlib","payload":"!"})
  with self.assertRaises(ValueError):decode_game_data(packed,limit=4)
 def test_manifest_selects_legacy_not_presence_of_modern_helpers(self):
  self.assertEqual(contract(True)["dialect"],"legacy")
  self.assertEqual(contract()["dialect"],"modern")
  with self.assertRaises(ValueError):client_contract({"setup":{}},['40021 48775'])
 def test_uuid_starting_mode_does_not_invent_a_purchase(self):
  plan=discover_modes(cfg(),contract(),[SOURCE]);self.assertFalse(plan["unresolved"])
  self.assertEqual([x["kind"] for x in plan["modes"]],["SPIN"])
  self.assertEqual(plan["domains"]["purchase"]["options"],[])
 def test_server_options_not_prices_determine_semantics(self):
  c=cfg([{"uuid":"a","name":"default","cost":10},{"uuid":"b","name":"extra","cost":12},{"uuid":"c","name":"BuyFeature","cost":1000}]);c["game"].update(activeBetOptions=["default","extra","BuyFeature"],extraBetEnabled=True,featureBetEnabled=True)
  p=discover_modes(c,contract(),[SOURCE]);self.assertEqual([x["kind"] for x in p["modes"]],["SPIN","ANTE_BET","PURCHASE"])
  self.assertEqual(p["domains"]["ante"]["options"],["b"])
  c["game"]["activeBetOptions"]=["default","extra"]
  self.assertEqual(len(discover_modes(c,contract(),[SOURCE])["modes"]),2)
 def test_extra_bet_from_current_client_is_ante_only_with_binding(self):
  c=cfg([{"uuid":"base","name":"default","cost":500},{"uuid":"extra-bet","name":"extraBet","cost":600}])
  c['game']['activeBetOptions']=['default','extraBet']
  bound=discover_modes(c,contract(),[SOURCE])
  self.assertEqual([m['kind'] for m in bound['modes']],['SPIN','ANTE_BET'])
  self.assertEqual(bound['domains']['ante']['options'],['extra-bet'])
  self.assertFalse(bound['unresolved'])
  unbound=discover_modes(c,contract(),['other client code'])
  self.assertEqual(unbound['modes'][1]['kind'],'UNKNOWN_FEATURE')
  self.assertTrue(unbound['unresolved'])

 def test_single_extrabet_without_binding_never_falls_back_to_base(self):
  c=cfg([{"uuid":"extra-bet","name":"extraBet","cost":600}])
  report=discover_modes(c,contract(),['other client code'])
  self.assertEqual(report['modes'][0]['kind'],'UNKNOWN_FEATURE')
  self.assertIn('BASE_MODE_UNBOUND',report['unresolved'])

 def test_unknown_cost_is_partial_and_not_silently_a_purchase(self):
  c=cfg([{"uuid":"a","name":"default","cost":10},{"uuid":"b","name":"Mystery","cost":900}]);p=discover_modes(c,contract(),[SOURCE]);self.assertTrue(p["unresolved"]);self.assertFalse(p["domains"]["purchase"]["complete"])
 def test_source_semantic_binding_required(self):
  c=cfg([{"uuid":"a","name":"default","cost":10},{"uuid":"b","name":"BF","cost":650}]);p=discover_modes(c,contract(),['generic platform only']);self.assertTrue(p["unresolved"])
 def test_legacy_and_modern_entries_use_different_selectors(self):
  mode=discover_modes(cfg(),contract(),[SOURCE])["modes"][0]
  modern=entry_command(mode,contract());legacy=entry_command(mode,contract(True))
  self.assertEqual(modern["featureType"],"Default");self.assertNotIn("betCost",legacy)
  self.assertEqual(legacy["gameData"]["stakeCostUuid"],"base-id")
 def test_modular_default_alias_does_not_send_capitalized_cost_name(self):
  c=client_contract({"setup":{"useExtendedBetApi":True}},[SOURCE+' baseCostName:"default"'])
  mode=discover_modes(cfg(),c,[SOURCE])["modes"][0]
  self.assertEqual(entry_command(mode,c)["featureType"],"default")
 def test_reject_invalid_money_or_duplicate_names(self):
  for values in [[{"uuid":"x","name":"a","cost":True}],[{"uuid":"a","name":"same","cost":10},{"uuid":"b","name":"same","cost":20}]]:
   with self.assertRaises(ValueError):discover_modes(cfg(values),contract(),[SOURCE])
 def test_pick_catalog_can_repeat_but_consumed_index_must_not(self):
  state=PickState();g={"nextRound":"P","listPickPlayerPickOptions":[{"index":1},{"index":2}],"playStack":[{"round":"P","modeType":"LIST_PICK","remainingPlayCount":1}]}
  self.assertEqual(state.parameters(g,True),[{"key":"pick","value":"1"}])
  g["playStack"].insert(0,{"round":"P","lastPlayInModeData":{"listPickData":{"payoutResults":[{"context":{"uiIndex":1}}]}}})
  self.assertEqual(state.parameters(g,True),[{"key":"pick","value":"2"}])
  with self.assertRaises(ValueError):PickState().parameters(g,False)
 def test_round_settlement_uses_cumulative_win_not_last_delta(self):
  ledger=RoundLedger(1000,"id",100)
  ledger.accept({"stakeAmount":100,"betCost":100,"winAmount":20,"gameRoundClosed":False,"gameData":{"stakeCostUuid":"id","totalWinAmount":20,"nextRound":"F"}})
  ledger.accept({"stakeAmount":0,"betCost":0,"winAmount":30,"gameRoundClosed":True,"gameData":{"stakeCostUuid":"id","totalWinAmount":50,"nextRound":"BET_END_STATE_IDENTIFIER"}})
  self.assertTrue(ledger.verify(950));self.assertFalse(ledger.verify(951))
 def test_continuation_cannot_charge_again(self):
  ledger=RoundLedger(1000,"id",100);ledger.accept({"stakeAmount":100,"winAmount":0,"gameData":{"stakeCostUuid":"id"}})
  with self.assertRaises(ValueError):ledger.accept({"stakeAmount":100,"winAmount":0,"gameData":{"stakeCostUuid":"id"}})
 def test_registry_routes_playtech_to_executable_adapter(self):
  from tester_spin.providers.registry import provider_class
  cls=provider_class("playtech");self.assertEqual(cls.__module__,"tester_spin.providers.playtech.adapter");self.assertTrue(cls.execution_supported)


class AdapterIntegrationTests(unittest.TestCase):
 def run_fixture(self, choices=False, ante=False):
  import tempfile, threading
  from pathlib import Path
  from tester_spin.models import Game
  from tester_spin.providers.playtech.adapter import PlaytechProvider
  modes=[{"uuid":"a","name":"default","cost":10}]
  if choices:modes.append({"uuid":"b","name":"BuyFeature","cost":100})
  if ante:modes.append({"uuid":"b","name":"extra","cost":12})
  configuration=cfg(modes)
  class Session:
   source_hashes=["synthetic"]
   manifest={"setup":{"usesLegacyBetApi":False}}
   sources=[SOURCE+' FGPickController parameters']
   config=[{"scope":{},"content":configuration}]
   def __init__(self,*args):self.balance=1000;self.errors=[];self.mode=None
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def wait(self,predicate,reason):
    if not predicate():raise ValueError(reason)
   def exchange(self,command,contract):
    entry=command['gameData']['ID']==40021
    if entry:self.mode=next(x for x in modes if x['name']==command['featureType'])
    charge=self.mode['cost'] if entry else 0;self.balance-=charge
    pick=choices and self.mode['uuid']=='b' and entry
    data={'_type':'ryota:GameResponse','stakeCostUuid':self.mode['uuid'],'totalWinAmount':0,'nextRound':'P' if pick else 'BET_END_STATE_IDENTIFIER'}
    if pick:data.update(listPickPlayerPickOptions=[{'index':1},{'index':2}],playStack=[{'round':'P','modeType':'LIST_PICK','remainingPlayCount':1}])
    return {'stakeAmount':charge,'betCost':charge,'winAmount':0,'gameRoundClosed':not pick,'gameData':data}
  with tempfile.TemporaryDirectory() as td:
   provider=PlaytechProvider(Path(td));provider.session_factory=Session
   result=provider.test_game(Game('playtech','fixture','Fixture','https://www.playtechone.com/fixture',symbol='gpas_fixture'),spins=1,timeout_s=5,stop_event=threading.Event(),progress=lambda _:None)
   if result.status=='OK':
    result=provider.finalize_test_result(result,progress=lambda _:None)
   return result
 def test_full_adapter_and_common_finalizer_accept_closed_base(self):
  result=self.run_fixture();self.assertEqual(result.status,'OK',result.error);self.assertEqual(result.successful_spins,2);self.assertTrue(result.structural_map['return_to_base_verified'])
 def test_common_finalizer_recognizes_completed_antebet(self):
  result=self.run_fixture(ante=True);self.assertEqual(result.status,'OK',result.error);self.assertEqual(result.successful_spins,3)
 def test_closed_purchase_reenters_to_cover_other_choices(self):
  result=self.run_fixture(True);self.assertEqual(result.status,'OK',result.error);self.assertFalse(result.structural_map['pending_choice_branches']);self.assertEqual(result.successful_spins,4)
 def test_non_gpas_does_not_start_a_browser(self):
  import tempfile,threading
  from pathlib import Path
  from tester_spin.models import Game
  from tester_spin.providers.playtech.adapter import PlaytechProvider
  with tempfile.TemporaryDirectory() as td:
   p=PlaytechProvider(Path(td));p.session_factory=lambda *a: self.fail('browser for unsupported engine')
   r=p.test_game(Game('playtech','fixture','Fixture','https://www.playtechone.com/fixture',symbol='other'),spins=1,timeout_s=1,stop_event=threading.Event(),progress=lambda _:None)
   self.assertEqual(r.status,'PARCIAL');self.assertFalse(r.attempts)
