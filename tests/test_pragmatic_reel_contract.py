import json
import unittest
from pathlib import Path
from tester_spin.providers.pragmatic_reel_contract import certify_reel_contract, discover_reel_contract, reel_selection

FIXTURE=json.loads(Path(__file__).with_name('fixtures').joinpath('pragmatic_reel_client.json').read_text())

class ReelContractTests(unittest.TestCase):
    def setUp(self):
        self.contract=certify_reel_contract(FIXTURE['source_excerpt'],source_url=FIXTURE['source_url'])
        self.response={'rs':'mc','rs_p':'0','rs_c':'1','rs_m':'1','sw':'5','trail':'pw~0.00;sr~2'}

    def test_certifies_client_data_flow_without_game_name(self):
        self.assertIsNotNone(self.contract)
        self.assertEqual(self.contract['trail_key'],'trail')
        self.assertEqual(self.contract['status_key'],'sr')
        self.assertEqual(self.contract['wire_field'],'ind')
        changed=FIXTURE['source_excerpt'].replace('RespinFeatureManager_ChCh','AnotherClientFeature')
        self.assertIsNotNone(certify_reel_contract(changed))

    def test_selects_response_default_and_records_full_client_domain(self):
        result=reel_selection(self.response,self.contract)
        self.assertEqual(result['fields'],{'ind':'2'})
        self.assertEqual(result['default'],'2')
        self.assertEqual(result['selected'],'2')
        self.assertEqual(result['domain'],[str(i) for i in range(32)])
        self.assertEqual(result['contract_source'],FIXTURE['source_url'])

    def test_override_is_a_reachable_toggle_mask(self):
        result=reel_selection(self.response,self.contract,override=29)
        self.assertEqual(result['fields'],{'ind':'29'})
        self.assertEqual(result['default'],'2')
        self.assertEqual(reel_selection(self.response,self.contract,override=0)['fields'],{'ind':'0'})
        for override in [-1,32,1.5,True,'bad']:
            with self.subTest(override=override),self.assertRaises(ValueError):
                reel_selection(self.response,self.contract,override=override)

    def test_only_active_multicase_response_applies(self):
        for extra in [{'rs':'t'},{'rs':'uw'},{'rs':''},{'rs_t':'1'},{'rs_t':'0'},{'rs_t':''},{'rs_t':None}]:
            self.assertIsNone(reel_selection(dict(self.response,**extra),self.contract))
        self.assertIsNone(reel_selection(self.response,None))

    def test_missing_invalid_or_ambiguous_default_never_invents_mask(self):
        for extra in [{'trail':'pw~1'},{'trail':'sr~32'},{'trail':'sr~-1'},{'trail':'sr~x'},{'trail':'sr~2;sr~3'},{'sw':'0'},{'sw':'1.5'},{'sw':'99'}]:
            with self.subTest(extra=extra),self.assertRaises(ValueError):
                reel_selection(dict(self.response,**extra),self.contract)

    def test_rejects_partial_or_changed_client_semantics(self):
        for old,new in [('^=reelMask','+=reelMask'),('extraParam.dict["ind"]','extraParam.other["ind"]'),('dataValue[0]==this.reelsStatusKey','dataValue[0]!=this.reelsStatusKey')]:
            self.assertIsNone(certify_reel_contract(FIXTURE['source_excerpt'].replace(old,new)))

    def test_discovery_follows_actual_platform_loader_and_build_revision(self):
        launch='UHT_ALL=true; UHT_CONFIG.GAME_URL+=(UHT_CONFIG.MINI_MODE?"mini":UHT_DEVICE_TYPE.MOBILE?"mobile":"desktop")+"/";Loader.LoadScript(UHT_CONFIG.GAME_URL+"bootstrap.js"+"?key="+"abc"); var config={"datapath":"https://demo.example/game/"};'
        bootstrap="UHT_SCRIPTS_SIZE='build.js?key=123:3000,';"
        texts={'https://demo.example/game/desktop/bootstrap.js?key=abc':bootstrap,'https://demo.example/game/desktop/build.js?key=123':FIXTURE['source_excerpt']}
        class Response:
            def __init__(self,text,url):self.text=text;self.url=url;self.content=text.encode()
            def raise_for_status(self):pass
        class Session:
            def __init__(self):self.urls=[]
            def get(self,url,**kwargs):self.urls.append(url);return Response(texts[url],url)
        session=Session()
        result=discover_reel_contract(session,launch,'https://demo.example/launch',timeout_s=1)
        self.assertEqual(result['wire_field'],'ind')
        self.assertEqual(session.urls,list(texts))

    def test_no_datapath_does_not_guess_network_paths(self):
        class Session:
            def get(self,*args,**kwargs):raise AssertionError('unexpected network')
        self.assertIsNone(discover_reel_contract(Session(),'<html/>','https://demo.example/game'))

