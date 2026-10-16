import json
import re
from pathlib import Path
from tester_spin.providers.ka_gaming.capabilities import client_declarations

FIXTURE=json.loads(Path('tests/fixtures/ka_oct11_declarations.json').read_text(encoding='utf-8'))
REF=json.loads(Path('tester_spin/providers/ka_gaming/declaration_reference.json').read_text(encoding='utf-8'))

def rename(source):
    names={'xd':'DescriptorBase','Uc':'BuyButton','Eba':'ButtonBase','oda':'buyEnabled','t$a':'anteEnabled','Oia':'makeButton','Xqa':'buyPrice','Ya':'controller','EQd':'disabledFlag','uoa':'publicDisable','YSb':'setPositions','cee':'canBuy','kW':'buyCommand','Ol':'stake','mj':'lines','ko':'ante','ti':'positions'}
    return re.sub(r'[A-Za-z_$][\w$]*',lambda m:names.get(m[0],m[0]),source)

def test_renamed_public_contract_preserves_declared_options():
    row=FIXTURE['games'][0]
    common=';'.join(REF['snippets'])
    result=client_declarations(rename(common),rename(row['client']),row['symbol'],row['initial'])
    assert result['domains']['purchase']['complete']
    assert result['domains']['purchase']['options']==['pos:1']

def test_changed_wire_selector_stays_unknown():
    row=FIXTURE['games'][0]
    common=rename(';'.join(REF['snippets'])).replace('[1]','[2]')
    assert not client_declarations(common,rename(row['client']),row['symbol'],row['initial'])['domains']['purchase']['complete']


def test_changed_button_literal_stays_unresolved():
    row=FIXTURE['games'][0]
    common=rename(';'.join(REF['snippets'])).replace('buy.feature.buy.font','unknown.font')
    assert not client_declarations(common,rename(row['client']),row['symbol'],row['initial'])['domains']['purchase']['complete']


def test_duplicate_matching_button_is_ambiguous():
    row=FIXTURE['games'][0]
    common=rename(';'.join(REF['snippets']+[REF['snippets'][1]]))
    assert not client_declarations(common,rename(row['client']),row['symbol'],row['initial'])['domains']['purchase']['complete']


def test_unknown_descriptor_override_remains_unresolved_after_renaming():
    row=FIXTURE['games'][0]
    client=rename(row['client']).replace('return new BuyButton','return new UnknownButton')
    assert not client_declarations(rename(';'.join(REF['snippets'])),client,row['symbol'],row['initial'])['domains']['purchase']['complete']


def test_registration_string_is_never_renamed():
    from tester_spin.providers.ka_gaming.declaration_names import normalize_declaration_sources
    _,client=normalize_declaration_sources(rename(';'.join(REF['snippets'])),'var text="buyEnabled BuyButton DescriptorBase";')
    assert client=='var text="buyEnabled BuyButton DescriptorBase";'


def test_optional_current_public_cache():
    import pytest
    root=Path('data/ka-access-review-20261016')
    paths=[root/name for name in ('game.min.2080.js','threemonkeys.2080.js','jadequest.2080.js')]
    if not all(p.exists() for p in paths):pytest.skip('Public integration cache unavailable')
    common=paths[0].read_text(encoding='utf-8')
    for path,symbol,options in ((paths[1],'ThreeMonkeys',[]),(paths[2],'JadeQuest',['pos:1'])):
        result=client_declarations(common,path.read_text(encoding='utf-8'),symbol,{'dbf':False})
        assert result['domains']['purchase']['complete']
        assert result['domains']['purchase']['options']==options
        assert result['domains']['ante']['complete']
