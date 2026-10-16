from tester_spin.models import Game,GameTestResult
from tester_spin.providers.redtiger.farm_adapter import RedTigerProvider


def test_modifier_export_keeps_exact_mode_and_price_contract(tmp_path):
    p=RedTigerProvider(tmp_path);g=Game('redtiger','neutral','Neutral','https://example.invalid',symbol='1')
    r=GameTestResult('redtiger','neutral','Neutral',g.url,1,1,0,'PARCIAL')
    r.discovered_modes=[{'id':'ANTE_BET_7','kind':'ANTE_BET','gameMode':7,'price_multiplier':'3',
        'server_type':'chanceIncrease','source':'SETTINGS.game.gameModes_and_mathModes_exact_match',
        'observed':True,'executable':True,'validated':True,'required_options':['7'],'covered_options':['7'],
        'modifier_contract':'redtiger/settings-mode-receipt/v1'}]
    c=p.build_farm_contract(g,r)
    assert c['modes'][0]['options']['gameMode']==7
    assert c['modes'][0]['options']['price_multiplier']=='3'
    c['protocol']['static'].pop('settings_mode_primitive')
    assert 'REDTIGER_SETTINGS_MODE_CONTRACT_REQUIRED' in p.validate_farm_contract(c)
