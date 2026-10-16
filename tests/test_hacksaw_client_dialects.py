import pytest
from tester_spin.providers.hacksaw.runtime import client_feature_types,discover_modes

BASE='x["hacksaw.common.types.FeatureBuyItem"]=Q;function Q(id,label,type){this.bonusGameId=id;this.featureBuyItemType=null;null!=type&&(this.featureBuyItemType=type)}'
DEFAULT='get_featureBuyItemType:function(){var t=this.featureBuyItemType;return null==t?S.startsWith(this.bonusGameId,"mod_")?"FeatureSpinItem":S.startsWith(this.bonusGameId,"bob_")?"BestOfBonusItem":"BonusBuyItem":t}'


def test_alternative_menu_methods_and_ternary_domains_are_union_not_first_only():
    source=BASE+DEFAULT+'getFeatureBuyItems:function(){return[new Q("base","",null)]}getFeatureBuyItems:function(on){return(on=null==on?!1:on)?[new Q("mod_high","",null)]:[new Q("base","",null)]}'
    assert client_feature_types(source)=={'base':'BonusBuyItem','mod_high':'FeatureSpinItem'}


def test_conflicting_roles_across_menu_methods_are_not_merged():
    source=BASE+'getFeatureBuyItems:function(){return[new Q("same","","BonusBuyItem")]}getFeatureBuyItems:function(){return[new Q("same","","FeatureSpinItem")]}'
    assert client_feature_types(source)=={}


BOOLEAN='x["hacksaw.common.types.FeatureBuyItem"]=Q;function Q(id,label,special){this.bonusGameId=id;this.isFeatureSpin=null;null!=special&&(this.isFeatureSpin=special)}Q.prototype={get_isFeatureSpin:function(){var a=this.isFeatureSpin;return null==a?S.startsWith(this.bonusGameId,"mod_"):a}};'


def test_legacy_boolean_role_keeps_explicit_override_and_proven_default():
    source=BOOLEAN+'getFeatureBuyItems:function(){return[new Q("bonus","",null),new Q("mod_feature","",null),new Q("mod_override","",!1)]}'
    assert client_feature_types(source)=={'bonus':'BonusBuyItem','mod_feature':'FeatureSpinItem','mod_override':'BonusBuyItem'}


def test_legacy_boolean_without_its_getter_contract_remains_unknown():
    source=BOOLEAN.replace('S.startsWith(this.bonusGameId,"mod_")','unknown(this.bonusGameId)')+'getFeatureBuyItems:function(){return[new Q("bonus","",null)]}'
    assert client_feature_types(source).get('bonus') in (None,'UNRESOLVED_CLIENT_TYPE')


def test_nullable_role_is_purchase_only_when_direct_client_consumer_proves_no_feature_spin():
    consumer='roundStarted:function(item){item=null!=item?item.featureBuyItemType:null;model.featureSpinActive=null!=item&&"FeatureSpinItem"==item}'
    source=BASE+consumer+'getFeatureBuyItems:function(){return[new Q("plain","",null)]}'
    assert client_feature_types(source)=={'plain':'BonusBuyItem'}
    assert client_feature_types(source.replace('null!=item&&"FeatureSpinItem"==item','unknown(item)'))=={'plain':'UNRESOLVED_CLIENT_TYPE'}



def test_explicit_boolean_role_cannot_override_an_unknown_client_getter():
    source=BOOLEAN.replace('S.startsWith(this.bonusGameId,"mod_")','unknown(this.bonusGameId)')+'getFeatureBuyItems:function(){return[new Q("bonus","",!0)]}'
    assert client_feature_types(source).get('bonus') in (None,'UNRESOLVED_CLIENT_TYPE')
