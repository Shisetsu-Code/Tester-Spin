import pytest
from tester_spin.providers.nolimit_city.choices import choice_domain,confirm_choice
WIRE='pickAndClickBet(e,t=!0){const i={selectedIndex:e.toString()},n={type:s.APIBetType.ZERO_BET,bet:"0.00",playerInteraction:i};this.sendRequest(n,!t)}'
SOURCE='''{1(m,e,r){const p=r(3),v=r(4);class Host{}e.NeutralHost=Host;Host.panel=new v.Panel;const idle=new p.Pick;Host.gameFlowController.addGameModeFlowStatePresentationMap("UNSEEN_PICK",new Map([[s.FlowState.IDLE,idle]]));bonusGame:{options:[{id:7},{id:9}],type:s.ASBonusPickOptions.PICK_MODE,pickNeededForModes:["UNSEEN_PICK"]}},3(m,e,r){const h=r(1);e.Pick=class{start(t){this.controller=t,h.NeutralHost.panel.show(x=>this.complete(x),h.NeutralHost.apiPlugin.isReplay)}complete(x){this.controller.finish(),h.NeutralHost.apiPlugin.betHandler.pickAndClickBet(x,!1)}}},4(m,e,r){const h=r(1);class Panel{constructor(){this.left=new b.Button(k.LEFT,()=>this.onClick(k.LEFT)),this.right=new b.Button(k.RIGHT,()=>this.onClick(k.RIGHT))}show(cb,replay){this.callback=cb}onClick(x){h.NeutralHost.model.data.bonusState.repeat=x===k.RIGHT,h.NeutralHost.setMode("UNSEEN_BONUS"),this.callback(x===k.RIGHT?9:7)}}e.Panel=Panel}}'''+WIRE
ANSWER={'game':{'nextMode':'UNSEEN_PICK','bonusState':{'repeat':False}}}

def test_client_bound_static_menu_uses_nested_boolean_ack_from_same_click():
    domain=choice_domain(SOURCE,ANSWER)
    assert domain['options']==[7,9] and domain['ack_path']==['bonusState','repeat']
    confirm_choice(domain,9,{'game':{'nextMode':'UNSEEN_BONUS','bonusState':{'repeat':True}}})
    confirm_choice(domain,7,{'game':{'nextMode':'UNSEEN_BONUS','bonusState':{'repeat':False}}})

@pytest.mark.parametrize('value',[False,None,1,'true'])
def test_nested_boolean_ack_must_match_selected_literal(value):
    domain=choice_domain(SOURCE,ANSWER)
    with pytest.raises(ValueError):confirm_choice(domain,9,{'game':{'bonusState':{'repeat':value}}})

@pytest.mark.parametrize('change',['wrongphase','wrongactiveclass','wrongcallback','wrongpredicate','wrongids','missingwire','missingfield','missingbutton'])
def test_nested_boolean_choice_requires_complete_binding_and_receipt_proof(change):
    source=SOURCE;answer=ANSWER
    if change=='wrongphase':source=source.replace('Map("UNSEEN_PICK"','Map("OTHER_PICK"')
    elif change=='wrongactiveclass':source=source.replace('idle=new p.Pick','idle=new p.Other')
    elif change=='wrongcallback':source=source.replace('this.callback(x===','this.otherCallback(x===')
    elif change=='wrongpredicate':source=source.replace('repeat=x===k.RIGHT','repeat=x===k.LEFT')
    elif change=='wrongids':source=source.replace('?9:7','?9:8')
    elif change=='missingwire':source=source.replace(WIRE,'')
    elif change=='missingfield':answer={'game':{'nextMode':'UNSEEN_PICK'}}
    elif change=='missingbutton':source=source.replace('()=>this.onClick(k.RIGHT)','()=>this.otherClick(k.RIGHT)')
    with pytest.raises(ValueError):choice_domain(source,answer)

@pytest.mark.parametrize('source',[
    SOURCE.replace('this.callback(x===k.RIGHT?9:7)','if(false)this.callback(x===k.RIGHT?9:7)'),
    SOURCE.replace('this.callback(x===k.RIGHT?9:7)','if(false){this.callback(x===k.RIGHT?9:7)}'),
    SOURCE.replace('h.NeutralHost.model.data.bonusState.repeat=x===k.RIGHT','if(false)h.NeutralHost.model.data.bonusState.repeat=x===k.RIGHT')
])
def test_dead_callback_or_conditional_predicate_cannot_supply_choice_authority(source):
    with pytest.raises(ValueError):choice_domain(source,ANSWER)

def test_nested_boolean_ack_also_requires_the_source_declared_return_phase():
    domain=choice_domain(SOURCE,ANSWER)
    for target in ['OTHER_BONUS','UNSEEN_PICK',None]:
        with pytest.raises(ValueError):confirm_choice(domain,7,{'game':{'nextMode':target,'bonusState':{'repeat':False}}})

BODY='h.NeutralHost.model.data.bonusState.repeat=x===k.RIGHT,h.NeutralHost.setMode("UNSEEN_BONUS"),this.callback(x===k.RIGHT?9:7)'
TIMED_BODY='h.NeutralHost.model.data.bonusState.repeat=x===k.RIGHT;const tl=new n.TimelineLite;tl.add(()=>{h.NeutralHost.setMode("UNSEEN_BONUS")});tl.add(()=>{this.callback(x===k.RIGHT?9:7)})'

@pytest.mark.parametrize('body',[
    'return;'+BODY,
    'throw new Error("stop");'+BODY,
    'if(this.blocked)return;'+BODY,
    BODY.replace(',h.NeutralHost.setMode',';return;h.NeutralHost.setMode'),
    BODY.replace(',this.callback',';throw new Error("stop");this.callback'),
    TIMED_BODY.replace('tl.add(()=>{h.NeutralHost','return;tl.add(()=>{h.NeutralHost'),
    TIMED_BODY.replace('()=>{h.NeutralHost','()=>{return;h.NeutralHost'),
    TIMED_BODY.replace('()=>{h.NeutralHost','()=>{throw new Error("stop");h.NeutralHost'),
    TIMED_BODY.replace('()=>{this.callback','()=>{return;this.callback'),
    TIMED_BODY.replace('()=>{this.callback','()=>{throw new Error("stop");this.callback'),
])
def test_early_exit_before_required_pick_effect_never_supplies_authority(body):
    with pytest.raises(ValueError):choice_domain(SOURCE.replace(BODY,body),ANSWER)

def test_active_timeline_pick_effects_remain_proven():
    domain=choice_domain(SOURCE.replace(BODY,TIMED_BODY),ANSWER)
    assert domain['target_phase']=='UNSEEN_BONUS'
