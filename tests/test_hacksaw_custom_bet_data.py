import unittest
from tester_spin.providers.hacksaw.custom_bet_data import client_custom_bet_data

SDK = '\x22updateCustomBetData\x22,function(t){e._gameState.customBetData=t} O.customData=this._gameState.customBetData;var Z={bets:[O]}'
SOURCE = '''registry["hacksaw.common.types.FeatureBuyItem"]=Item;init:function(){this._casinoChannel.publish("updateCustomBetData",{risk:"calm"})},update:function(){var u=n.flag?{data:{risk:"high"}}:{data:{risk:"calm"}};this._casinoChannel.publish("updateCustomBetData",u.data);this._uiChannel.publish("updateFeatureBuyContent",new Menu(this.getFeatureBuyItems(n.flag)))},getFeatureBuyItems:function(e){return(e=null==e?!1:e)?[new Item("alpha",null)]:[new Item("beta",null)]}'''
class CustomBetDataTests(unittest.TestCase):
    def test_literal_default_and_boolean_bound_selectors(self):
        result=client_custom_bet_data(SOURCE,SDK)
        self.assertEqual(result['default'],{'risk':'calm'})
        self.assertEqual(result['by_selector'],{'alpha':{'risk':'high'},'beta':{'risk':'calm'}})
    def test_missing_transport_proof_is_unresolved(self):
        self.assertFalse(client_custom_bet_data(SOURCE,'')['proven'])
    def test_mismatched_flag_is_unresolved(self):
        self.assertEqual(client_custom_bet_data(SOURCE.replace('getFeatureBuyItems(n.flag)','getFeatureBuyItems(n.other)'),SDK)['by_selector'],{})
    def test_bet_override_is_not_accepted(self):
        result=client_custom_bet_data(SOURCE.replace('risk:"calm"','betAmount:100'),SDK)
        self.assertIsNone(result['default'])
    def test_dynamic_payload_is_unresolved(self):
        result=client_custom_bet_data(SOURCE.replace('{risk:"calm"}','{risk:getRisk()}'),SDK)
        self.assertIsNone(result['default'])

    def test_menu_container_alias_is_bound(self):
        source=SOURCE.replace('this._uiChannel.publish("updateFeatureBuyContent",new Menu(this.getFeatureBuyItems(n.flag)))','r=new Menu(this.getFeatureBuyItems(n.flag),new Other(4,1));this._uiChannel.publish("updateFeatureBuyContent",r)')
        self.assertEqual(client_custom_bet_data(source,SDK)['by_selector']['alpha'],{'risk':'high'})

    def test_literal_publish_outside_init_is_not_default(self):
        self.assertIsNone(client_custom_bet_data(SOURCE.replace('init:function','click:function'),SDK)['default'])
    def test_missing_bets_transport_is_unresolved(self):
        self.assertFalse(client_custom_bet_data(SOURCE,SDK.replace('bets:[O]','other:[O]'))['proven'])
    def test_conflicting_default_is_unresolved(self):
        source=SOURCE.replace('},update:function',';this._casinoChannel.publish("updateCustomBetData",{risk:"other"})},update:function')
        self.assertIsNone(client_custom_bet_data(source,SDK)['default'])
    def test_alias_reassignment_is_unresolved(self):
        source=SOURCE.replace('this._uiChannel.publish("updateFeatureBuyContent",new Menu(this.getFeatureBuyItems(n.flag)))','r=new Menu(this.getFeatureBuyItems(n.flag));r=unknown;this._uiChannel.publish("updateFeatureBuyContent",r)')
        self.assertEqual(client_custom_bet_data(source,SDK)['by_selector'],{})

    def test_unknown_menu_constructor_is_unresolved(self):
        self.assertEqual(client_custom_bet_data(SOURCE.replace('new Item(', 'new Other('),SDK)['by_selector'],{})

    def test_context_alias_cannot_change_before_publish(self):
        for mutation in ('u={data:{risk:"other"}};', 'u.data={risk:"other"};', 'u.data.risk="other";', 'mutate(u);'):
            with self.subTest(mutation=mutation):
                source=SOURCE.replace('this._casinoChannel.publish("updateCustomBetData",u.data)', mutation+'this._casinoChannel.publish("updateCustomBetData",u.data)')
                self.assertEqual(client_custom_bet_data(source,SDK)['by_selector'],{})

    def test_selector_flag_cannot_change_before_menu_consumption(self):
        for mutation in ('n.flag=!n.flag;', 'n=other;', 'n["flag"]=false;', 'mutate(n);', 'n.flag++;', 'n.flag&&=false;', 'n.flag||=true;', 'n.flag??=true;'):
            with self.subTest(mutation=mutation):
                source=SOURCE.replace('this._uiChannel.publish("updateFeatureBuyContent",', mutation+'this._uiChannel.publish("updateFeatureBuyContent",')
                self.assertEqual(client_custom_bet_data(source,SDK)['by_selector'],{})
