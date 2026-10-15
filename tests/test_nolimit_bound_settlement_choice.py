import copy,json
from decimal import Decimal
from pathlib import Path
import pytest
from tester_spin.providers.nolimit_city.contracts import resolve_operation,confirm_operation,observed_request_matches
from tester_spin.providers.nolimit_city.runtime import RoundLedger,NolimitSession
from tester_spin.providers.nolimit_city.declarations import declared_options

F=json.loads((Path(__file__).parent/'fixtures/nolimit_bound_settlement_choice.json').read_text())

def mode_for(root):
    modes,_=declared_options(F['init'])
    return {**next(m for m in modes if m.get('selector')==root['request']['featureName']),'stake':root['request']['bet']}

@pytest.mark.parametrize('index',[0,1,2])
def test_captured_settlement_buttons_and_wallet_are_reconciled(index):
    root,pick=F['rounds'][index];mode=mode_for(root)
    before=Decimal(root['response']['balance'])+Decimal(mode['stake'])*Decimal(mode['price_multiplier'])
    ledger=RoundLedger(before,mode)
    assert not ledger.accept(root['response'],request=root['request'])
    contract=resolve_operation(ledger.last_answer,mode,raw_answer=root['response'],client_source=F['source'])
    assert contract['domain']['options']==([1] if index==2 else [0,1])
    assert contract['domain']['source']=='CLIENT_BOUND_SETTLEMENT_BUTTONS'
    matches,selected=observed_request_matches(contract,pick['request'])
    assert matches
    confirm_operation(contract,pick['response'],selected)
    assert ledger.accept(pick['response'],request=pick['request'],operation=contract)
    assert ledger.after==Decimal(pick['response']['balance'])


def test_normal_and_restricted_roots_discover_only_available_buttons(tmp_path):
    s=NolimitSession();s.choice_client=F['source']
    root,pick=F['rounds'][1];mode=mode_for(root)
    q=s.next_command(root['response'],tmp_path,mode['id'],mode)
    assert q['playerInteraction']=={'selectedIndex':'0'}
    s.confirm_pending_choice(pick['response'])
    assert not s.sync_choices(mode)
    q=s.next_command(root['response'],tmp_path,mode['id'],mode)
    assert q['playerInteraction']=={'selectedIndex':'1'}
    s.confirm_pending_choice(F['rounds'][0][1]['response'])
    assert s.sync_choices(mode)
    root,pick=F['rounds'][2];mode=mode_for(root)
    q=s.next_command(root['response'],tmp_path,mode['id'],mode)
    assert q['playerInteraction']=={'selectedIndex':'1'}
    s.confirm_pending_choice(pick['response'])
    assert s.sync_choices(mode)

@pytest.mark.parametrize('mutation',[
 lambda s:s.replace('pickAndClickBet(0,!1)','pickAndClickBet(unknown(),!1)'),
 lambda s:s.replace('bet:"0.00"','bet:"1.00"'),
 lambda s:s.replace('new R.Idle','new R.Unknown'),
 lambda s:s.replace('transitionScreen.enableDoubleOrNothing()','transitionScreen.otherPanel()'),
 lambda s:s.replace('this.isGodModeDeluxe="GOD_MODE_DELUXE"==this.buyFeatureName','this.isGodModeDeluxe=unknown()'),
 lambda s:s.replace('1==t&&this.gambleNoButton.enable(!0)','unknown()&&this.gambleNoButton.enable(!0)'),
])
def test_unproven_buttons_or_wire_binding_are_never_guessed(mutation):
    root=F['rounds'][0][0]
    with pytest.raises(ValueError):resolve_operation(root['response'],mode_for(root),client_source=mutation(F['source']))

@pytest.mark.parametrize('field,value',[('nextMode','FREESPIN'),('mode','NORMAL')])
def test_unsettled_or_wrong_phase_is_rejected(field,value):
    root,pick=F['rounds'][0];mode=mode_for(root)
    contract=resolve_operation(root['response'],mode,client_source=F['source'])
    answer=copy.deepcopy(pick['response']);answer['game'][field]=value
    with pytest.raises(ValueError):confirm_operation(contract,answer,1)


def test_literal_ids_are_read_from_client_not_inferred_from_har():
    root,pick=F['rounds'][1]
    source=F['source'].replace('pickAndClickBet(0,!1)','pickAndClickBet(7,!1)')
    contract=resolve_operation(root['response'],mode_for(root),client_source=source)
    assert contract['domain']['options']==[7,1]
    assert not observed_request_matches(contract,pick['request'])[0]


@pytest.mark.parametrize('mutation',[
 lambda s:s.replace('pickAndClickBet(0,!1)','pickAndClickBet(0,!1)',1).replace('o.ExampleSlot.apiPlugin.betHandler.pickAndClickBet(0,!1)','!1&&o.ExampleSlot.apiPlugin.betHandler.pickAndClickBet(0,!1)'),
 lambda s:s.replace('o.ExampleSlot.apiPlugin.betHandler.pickAndClickBet(0,!1)','()=>o.ExampleSlot.apiPlugin.betHandler.pickAndClickBet(0,!1)'),
 lambda s:s.replace('1==t&&this.gambleNoButton.enable(!0)','1==t&&this.gambleNoButton.enable(!0),this.gambleNoButton.enable(!1)'),
 lambda s:s.replace('this.gambleYesButton.enable(!0),1==t','this.gambleYesButton.enable(!0),this.gambleYesButton.enable(!1),1==t'),
 lambda s:s.replace('return n.gsap.timeline().add(()=>{this.yesButtonCallback','return n.gsap.timeline({paused:!0}).add(()=>{this.yesButtonCallback'),
])
def test_unreachable_dispatch_or_disabled_panel_never_declares_choice(mutation):
    root=F['rounds'][0][0]
    with pytest.raises(ValueError):resolve_operation(root['response'],mode_for(root),client_source=mutation(F['source']))


def test_export_requires_bound_button_contract(tmp_path):
    from tester_spin.providers.nolimit_city.adapter import SPEC,NolimitCityProvider
    root=F['rounds'][0][0]
    domain=resolve_operation(root['response'],mode_for(root),client_source=F['source'])['domain']
    domain={**domain,'covered':domain['options']}
    contract={'modes':[{'options':{'choice_domains':[domain]}}],
        'protocol':{'static':copy.deepcopy(SPEC.protocol_static)}}
    provider=NolimitCityProvider(tmp_path)
    assert 'NOLIMIT_BOUND_SETTLEMENT_SELECTION_REQUIRED' not in provider.validate_farm_contract(contract)
    contract['protocol']['static'].pop('bound_settlement_selection')
    assert 'NOLIMIT_BOUND_SETTLEMENT_SELECTION_REQUIRED' in provider.validate_farm_contract(contract)


@pytest.mark.parametrize('mutation',[
 lambda s:s.replace('this.gambleYesButton.enable(!0),1==t','!1&&this.gambleYesButton.enable(!0),1==t'),
 lambda s:s.replace('this.gambleYesButton.enable(!0),1==t','this.yesButtonCallback=()=>{},this.gambleYesButton.enable(!0),1==t'),
])
def test_panel_root_enabling_and_callback_identity_are_required(mutation):
    root=F['rounds'][0][0]
    with pytest.raises(ValueError):resolve_operation(root['response'],mode_for(root),client_source=mutation(F['source']))


def test_confirmation_panel_cannot_reassign_accept_to_decline():
    root=F['rounds'][0][0]
    source=F['source'].replace('this.enableDoubleOrNothing(!0)},this.gambleWarningText',
        'this.enableDoubleOrNothing(!0)},this.yesButtonCallback=this.doubleOrNothingNo,this.gambleWarningText')
    with pytest.raises(ValueError):resolve_operation(root['response'],mode_for(root),client_source=source)
