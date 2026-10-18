import pytest
from tester_spin.providers.playtech.adapter_config import projects,config_paths,merge_maps,mapped_kind


def test_project_and_maps_are_declarative_and_ordered():
    assert projects(['class Game{constructor(){super(options,"jmm/game.jmp")}}'])==['jmm/game.jmp']
    assert config_paths({'modules':{'unknown':{'jmms':['config/a.jmm','config/b.jmm']}}})==['config/a.jmm','config/b.jmm']
    maps=merge_maps([{'config':{'game_adapter':{'bet_features':{'regular':'base','extra_bet':'extraBet'}}}},{'config':{'game_adapter':{'bet_features':{'LuckyBoxBronze':'LuckyBoxBronze'},'bet_feature_types':{'regular':'regular','extra_bet':'extra_bet','lucky_box':'LuckyBox[Bronze|Silver|Gold|Diamond]'}}}}])
    assert mapped_kind('LuckyBoxBronze',maps)=='PURCHASE'
    assert mapped_kind('extraBet',maps)=='ANTE_BET'
    assert mapped_kind('base',maps)=='SPIN'
    assert mapped_kind('MadeUp',maps) is None


def test_paths_and_unbounded_or_ambiguous_patterns_are_rejected():
    with pytest.raises(ValueError):config_paths({'modules':{'unknown':{'jmms':['../secret.jmm']}}})
    with pytest.raises(ValueError):config_paths({'modules':{'phone':{'jmms':[]}}})
    with pytest.raises(ValueError):merge_maps([{'config':{'game_adapter':{'bet_features':{'bad':{}}}}}])
    assert mapped_kind('cost',{'bet_features':{'x':'cost'},'bet_feature_types':{'buy_feature':'(a+)+$'}}) is None
    assert mapped_kind('cost',{'bet_features':{'x':'cost'},'bet_feature_types':{'buy_feature':'x','extra_bet':'x'}}) is None


def test_conditional_ui_projects_are_not_merged_into_primary_config():
    assert projects(['class G{constructor(){super(o,"jmm/game.jmp")}selectProjects(){if(flag)list.push("jmm/bonus.jmp")}}'])==['jmm/game.jmp']


def test_encoded_parent_path_is_also_rejected():
    assert projects(['class G{constructor(){super(o,"jmm/%2e%2e/private.jmp")}}'])==[]
    with pytest.raises(ValueError):config_paths({'modules':{'unknown':{'jmms':['%2e%2e/private.jmm']}}})
