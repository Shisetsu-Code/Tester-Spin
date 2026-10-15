import copy,json
from pathlib import Path
import pytest
from tester_spin.providers.nolimit_city.runtime import RoundLedger,declaration,NolimitSession,Unlearned
def automatic_command(*args):
    from tester_spin.providers.nolimit_city.client_actions import automatic_command as command
    return command(*args)

FIXTURES=json.loads((Path(__file__).parent/'fixtures/nolimit_reference_five_2.json').read_text())

FLOW='e.Auto=class{start(t){this._flowStateController=t,o.SimplePresentationRunner.run(this._presentations,()=>this.complete(),e=>t.setSkipCallback(e))}complete(){n.SlotGame.apiPlugin.betHandler.zeroBet(),this._flowStateController.finish()}};const P=new C.Auto;g.gameFlowController.addGameModeFlowStatePresentationMap(b.Mode.UNSEEN_BONUS,new Map([[l.FlowState.IDLE,P],[l.FlowState.BET,O]]));'

def test_flow_binding_discovers_unseen_phase_without_name_allowlist():
    answer={'game':{'mode':'NORMAL','nextMode':'UNSEEN_BONUS','freespinsLeft':5},'remainingFreeSpins':5}
    assert automatic_command(FLOW,answer)=={'type':'zeroBet','bet':'0.00'}
    for source in (FLOW.replace('IDLE,P','IDLE,O'), FLOW.replace('zeroBet()','zeroBet({selectedIndex:1})'), FLOW.replace('complete(){','complete(){if(this.allow)'), FLOW.replace('const P=new C.Auto','const P=new C.Other')):
        assert automatic_command(source,answer) is None
    assert automatic_command(FLOW,{'game':{'nextMode':'NORMAL'}}) is None

def test_legacy_controller_does_not_require_positive_prize():
    source='class o extends s.ZeroBetController{calculateIsTriggered(e){return e.nextMode===n.GameMode.NORMAL_AVALANCHE}}t.Auto=o;this.ZERO_BETS=[()=>new l.Auto];initGameEvents(){o.EventHandler.addEventListener(this,n.BalanceEvent.ZERO_BET,e=>this.onZeroBet(e.params[0]))}onZeroBet(e){this._slotApi.betHandler.zeroBet(),x.counter(e)}'
    answer={'game':{'nextMode':'NORMAL_AVALANCHE','thisAvalancheWinnings':0,'reelsAfterCollapse':[[1]]}}
    assert automatic_command(source,answer)=={'type':'zeroBet','bet':'0.00'}
    assert automatic_command(source.replace('ZERO_BETS=[()=>new l.Auto]','ZERO_BETS=[]'),answer) is None
    assert automatic_command(source.replace('onZeroBet(e){this._slotApi.betHandler.zeroBet()','onZeroBet(e){this._slotApi.betHandler.zeroBet({pick:1})'),answer) is None

def test_explicit_avalanche_step_alias_rejects_conflicting_amounts():
    from tester_spin.providers.nolimit_city.operation_fields import step_win
    assert step_win({'thisAvalancheWinnings':0,'totalAvalancheRoundWinnings':5})==0
    with pytest.raises(ValueError):step_win({'thisAvalancheWinnings':1,'win':2})

@pytest.mark.parametrize('row',FIXTURES,ids=lambda row:row['reference'])
def test_recorded_steps_pass_ledger_without_inventing_closure(row):
    modes,_=declaration(row['init']);before=row['init']['balance'];ledger=None
    for step in row['steps']:
        request=step['request']
        if request['type']!='zeroBet':
            if ledger is not None:assert ledger.closed
            mode=next(m for m in modes if m['kind']=='SPIN') if request['type']=='normalBet' else next(m for m in modes if m.get('selector')==request['featureName'])
            ledger=RoundLedger(before,mode)
        closed=ledger.accept(copy.deepcopy(step['response']),request=request)
        if closed:before=ledger.after
    assert ledger.closed is (row['reference']=='infectious5')

def test_session_prefers_bound_automatic_action_over_choice(tmp_path):
    session=NolimitSession();session.choice_client=FLOW
    command=session.choice_command({'game':{'mode':'NORMAL','nextMode':'UNSEEN_BONUS','freespinsLeft':5}},tmp_path,'BUY')
    assert command=={'type':'zeroBet','bet':'0.00'}
    assert session.pending_choice is None

def test_inactive_selection_sentinel_never_becomes_choice():
    from tester_spin.providers.nolimit_city.choices import choice_domain
    source='options:[{id:1},{id:2}],type:o.ASBonusPickOptions.PICK_MODE,pickNeededForModes:[a.Mode.FREESPIN_PICK]'
    with pytest.raises(ValueError):choice_domain(source,{'game':{'nextMode':'NORMAL','playerFSSelection':-1}})
    domain=choice_domain(source,{'game':{'nextMode':'FREESPIN_PICK','playerFSSelection':-1}})
    assert domain['options']==[1,2] and domain['ack_field']=='playerFSSelection'




@pytest.mark.parametrize('case',json.loads((Path(__file__).parent/'fixtures/nolimit_client_action_bindings.json').read_text()),ids=lambda case:case['reference'])
def test_official_client_bindings_from_reference_sample(case):
    assert automatic_command(case['source'],case['answer'])=={'type':'zeroBet','bet':'0.00'}
    # A paid extra-spin quote cannot be executed as a free automatic continuation.
    paid=copy.deepcopy(case['answer']);paid['game']['extraSpinCost']=10
    assert automatic_command(case['source'],paid) is None


def test_automatic_continuation_requires_server_phase_ack(tmp_path):
    session=NolimitSession();session.choice_client=FLOW
    session.choice_command({'game':{'mode':'NORMAL','nextMode':'UNSEEN_BONUS','freespinsLeft':5}},tmp_path,'BUY')
    with pytest.raises(Unlearned):session.confirm_pending_choice({'game':{'mode':'OTHER','nextMode':'NORMAL'}})
    session.confirm_pending_choice({'game':{'mode':'UNSEEN_BONUS','nextMode':'NORMAL'}})
    assert session.pending_automatic is None

@pytest.mark.parametrize('value',[None,True,-1,'NaN'])
def test_automatic_continuation_rejects_invalid_extra_quote(value):
    answer={'game':{'nextMode':'UNSEEN_BONUS','extraSpinCost':value}}
    assert automatic_command(FLOW,answer) is None


def test_pending_respin_cannot_settle_even_with_zero_free_spin_counter():
    from tester_spin.providers.nolimit_city.state import settled_state
    answer={'game':{'nextMode':'NORMAL','freespinsLeft':0,'respinActive':True},'features':{'available':[]},'remainingFreeSpins':0}
    assert not settled_state(answer)



def test_unknown_enclosing_condition_does_not_authorize_legacy_else_branch():
    case=next(case for case in json.loads((Path(__file__).parent/'fixtures/nolimit_client_action_bindings.json').read_text()) if case['reference']=='infectious5')
    source=case['source'].replace('return t.add(()=>{if(', 'return t.add(()=>{if(this.allowed){if(')
    source=source.replace('setZeroBetSpinCounter(i)}),t}', 'setZeroBetSpinCounter(i)}}),t}')
    assert automatic_command(source,case['answer']) is None



def test_unknown_enclosing_guard_blocks_normal_respin_dispatch():
    case=next(case for case in json.loads((Path(__file__).parent/'fixtures/nolimit_client_action_bindings.json').read_text()) if case['reference']=='base-respin')
    source=case['source'].replace('else{let e=-1;if(this._wildOverlays','else{if(this.allowed){let e=-1;if(this._wildOverlays')
    source=source.replace('setRespinSignAnimation(this._isRestore&&e<=0?-1:--e)}','setRespinSignAnimation(this._isRestore&&e<=0?-1:--e)}}')
    assert automatic_command(source,case['answer']) is None
