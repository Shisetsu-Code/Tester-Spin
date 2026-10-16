from pathlib import Path
import pytest
from tester_spin.providers.nolimit_city.choices import choice_domain,confirm_choice

CACHE=Path('data/providers/nolimit_city/_clients/Loner/1.1.11.js')
ANSWER={'game':{'mode':'NORMAL','nextMode':'FEATURE_TICK_TICK_BOOM'}}

@pytest.mark.skipif(not CACHE.is_file(),reason='Exact public client cache not supplied')
def test_variable_ui_selector_has_finite_buttons_and_a_distinct_phase_result_receipt():
    domain=choice_domain(CACHE.read_text(encoding='utf-8'),ANSWER)
    assert domain['options']==[1,2,3]
    assert domain['source']=='CLIENT_BOUND_LITERAL_BUTTONS'
    assert domain['result_path']==['featureInfo','timesBetWinDraw']
    confirm_choice(domain,2,{'game':{'mode':'FEATURE_TICK_TICK_BOOM','nextMode':'NORMAL','featureInfo':{'timesBetWinDraw':4.5}}})
    for game in [
        {'mode':'WRONG','nextMode':'NORMAL','featureInfo':{'timesBetWinDraw':4.5}},
        {'mode':'FEATURE_TICK_TICK_BOOM','nextMode':'NORMAL','featureInfo':{}},
        {'mode':'FEATURE_TICK_TICK_BOOM','nextMode':'NORMAL','featureInfo':{'timesBetWinDraw':True}},
        {'mode':'FEATURE_TICK_TICK_BOOM','nextMode':'NORMAL','featureInfo':{'timesBetWinDraw':-1}},
    ]:
        with pytest.raises(ValueError):confirm_choice(domain,2,{'game':game})

@pytest.mark.skipif(not CACHE.is_file(),reason='Exact public client cache not supplied')
@pytest.mark.parametrize('old,new',[
    ('pickAndClickBet(t,!1)','pickAndClickBet(1,!1)'),
    ('t=>this.onClicked(3)','t=>this.onClicked(4)'),
    ('this._onSelectedCallback(t);const i=', 'return;this._onSelectedCallback(t);const i='),
])
def test_variable_selector_rejects_changed_forwarding_buttons_or_dead_callback(old,new):
    source=CACHE.read_text(encoding='utf-8')
    assert old in source
    with pytest.raises(ValueError):choice_domain(source.replace(old,new),ANSWER)

@pytest.mark.skipif(not CACHE.is_file(),reason='Exact public client cache not supplied')
@pytest.mark.parametrize('old,new',[
    ('selectedIndex:t.toString()','selectedIndex:"99"'),
    ('vt.tickTickBoomView=new R.LonerTickTickBoomView','vt.tickTickBoomView=unknown,vt.tickTickBoomView=new R.LonerTickTickBoomView'),
    ('this._onSelectedCallback=t,this.init()','this._onSelectedCallback=t,this._onSelectedCallback=unknown,this.init()'),
])
def test_variable_selector_rejects_changed_wire_or_competing_bindings(old,new):
    source=CACHE.read_text(encoding='utf-8')
    assert old in source
    with pytest.raises(ValueError):choice_domain(source.replace(old,new),ANSWER)

@pytest.mark.skipif(not CACHE.is_file(),reason='Exact public client cache not supplied')
def test_button_constructor_cannot_ignore_the_supplied_selection_callback():
    source=CACHE.read_text(encoding='utf-8')
    assert 'super(t,n),this._currentState=0' in source
    with pytest.raises(ValueError):choice_domain(source.replace('super(t,n),this._currentState=0','super(t,()=>{}),this._currentState=0'),ANSWER)

@pytest.mark.skipif(not CACHE.is_file(),reason='Exact public client cache not supplied')
@pytest.mark.parametrize('old,new',[
    ('this._selection=t,a.SlotGame.apiPlugin.betHandler','this._selection=t,t=99,a.SlotGame.apiPlugin.betHandler'),
    ('onClick(t){if(this.interactive&&null!=this.parent){for(let t of this._clickCallbacks)t();','onClick(t){if(!1){for(let t of this._clickCallbacks)t();'),
])
def test_literal_callback_parameter_and_pointer_path_cannot_be_rewritten(old,new):
    source=CACHE.read_text(encoding='utf-8')
    assert old in source
    with pytest.raises(ValueError):choice_domain(source.replace(old,new),ANSWER)


@pytest.mark.parametrize('amount',[0,'3.50',9])
def test_phase_result_receipt_does_not_require_prize_to_equal_button_id(amount):
    domain={'state':'CHOICE_PHASE','options':[2,5],'available':[2,5],
        'source':'CLIENT_BOUND_LITERAL_BUTTONS','ack_field':'outcome','result_path':['outcome','amount'],'target_phase':'NORMAL'}
    confirm_choice(domain,5,{'game':{'mode':'CHOICE_PHASE','nextMode':'NORMAL','outcome':{'amount':amount}}})


@pytest.mark.parametrize('amount',[True,None,-1,'NaN','Infinity',{}])
def test_phase_result_receipt_rejects_missing_or_invalid_money(amount):
    domain={'state':'CHOICE_PHASE','options':[2,5],'available':[2,5],
        'source':'CLIENT_BOUND_LITERAL_BUTTONS','ack_field':'outcome','result_path':['outcome','amount'],'target_phase':'NORMAL'}
    with pytest.raises(ValueError):
        confirm_choice(domain,5,{'game':{'mode':'CHOICE_PHASE','nextMode':'NORMAL','outcome':{'amount':amount}}})

@pytest.mark.skipif(not CACHE.is_file(),reason='Exact public client cache not supplied')
@pytest.mark.parametrize('old,new',[
    ('e.SimplePresentationRunner=i}', 'e.SimplePresentationRunner=i;i.run=unknown}'),
    ('static run(t,e,n){const o=t.concat()', 'static run(t,e,n){return;const o=t.concat()'),
    ('start(t){this._flowStateController=t,n.SimplePresentationRunner.run(this._presentations,()=>this.complete(),e=>t.setSkipCallback(e))}', 'start(t){return;this._flowStateController=t,n.SimplePresentationRunner.run(this._presentations,()=>this.complete(),e=>t.setSkipCallback(e))}'),
    ('this._boundEvents||(this.bindEvents(),this._boundEvents=!0)', 'this._boundEvents||(this._boundEvents=!0)'),
])
def test_literal_selector_requires_actual_runner_and_pointer_listener_execution(old,new):
    source=CACHE.read_text(encoding='utf-8')
    assert old in source
    with pytest.raises(ValueError):choice_domain(source.replace(old,new),ANSWER)
