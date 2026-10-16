import pytest
from tester_spin.providers.nolimit_city.client_actions import _block
from tester_spin.providers.nolimit_city.fixed_signals import fixed_signal_command
WIRE='pickAndClickBet(e,t=!0){const i={selectedIndex:e.toString()},n={type:s.APIBetType.ZERO_BET,bet:"0.00",playerInteraction:i};this.sendRequest(n,!t)}'
SOURCE='''{1(m,e,r){const p=r(3),v=r(4);class Host{init(){Host.panel=new v.Panel;const idle=new p.Signal;Host.gameFlowController.addGameModeFlowStatePresentationMap("UNSEEN_SIGNAL",new Map([[s.FlowState.IDLE,idle]]))}}e.NeutralHost=Host;automaticPickGame:{optionSelection:e=>7,type:s.ASBonusPickOptions.PICK_MODE,pickNeededForModes:["UNSEEN_SIGNAL"]}},3(m,e,r){const h=r(1);e.Signal=class{start(t){this.controller=t,h.NeutralHost.panel.showView(x=>{this.done(x)},h.NeutralHost.apiPlugin.isReplay)}done(x){this.controller.finish(),h.NeutralHost.apiPlugin.betHandler.pickAndClickBet(x,!1)}}},4(m,e,r){const h=r(1);class Panel{constructor(){this.button=new Button("signal",()=>this.clicked())}showView(cb,replay){this.callback=cb}clicked(){this.enable(!1),this.pressed()}pressed(){const tl=n.gsap.timeline({onStart:()=>{if(!h.NeutralHost.apiPlugin.isReplay){if(null==this.callback)throw new Error("missing callback");this.callback(7),this.callback=void 0}}});return tl}}e.Panel=Panel}}'''+WIRE
ANSWER={'game':{'nextMode':'UNSEEN_SIGNAL'}}

def test_exact_client_fixed_signal_is_one_zero_stake_command():
    assert fixed_signal_command(SOURCE,ANSWER,_block)=={'type':'zeroBet','bet':'0.00','playerInteraction':{'selectedIndex':'7'}}

@pytest.mark.parametrize('change',['promoonly','wrongconstant','unknownphase','inactivepresentation','inactiveview','wire','conditionalcallback','replayonly','earlyreturn','wrongforwarding','alternatecallback'])
def test_fixed_signal_needs_complete_current_phase_and_active_callback_binding(change):
    source=SOURCE;answer=ANSWER
    if change=='promoonly':source=SOURCE.split('},3(m,e,r)')[0]+WIRE
    elif change=='wrongconstant':source=source.replace('this.callback(7)','this.callback(8)')
    elif change=='unknownphase':answer={'game':{'nextMode':'OTHER_SIGNAL'}}
    elif change=='inactivepresentation':source=source.replace('idle=new p.Signal','idle=new p.Other')
    elif change=='inactiveview':source=source.replace('Host.panel=new v.Panel','Host.panel=new v.Other')
    elif change=='wire':source=source.replace('bet:"0.00"','bet:"1.00"')
    elif change=='conditionalcallback':source=source.replace('this.callback(7)','if(this.enabled)this.callback(7)')
    elif change=='replayonly':source=source.replace('if(!h.NeutralHost.apiPlugin.isReplay)','if(h.NeutralHost.apiPlugin.isReplay)')
    elif change=='earlyreturn':source=source.replace('pressed(){','pressed(){return;')
    elif change=='wrongforwarding':source=source.replace('pickAndClickBet(x,!1)','pickAndClickBet(8,!1)')
    elif change=='alternatecallback':source=source.replace('clicked(){','other(){this.callback(8)}clicked(){')
    assert fixed_signal_command(source,answer,_block) is None

@pytest.mark.parametrize('source',[
    SOURCE.replace('showView(cb,replay){this.callback=cb}','showView(cb,replay){this.callback=cb,this.callback=other}'),
    SOURCE.replace('e.NeutralHost=Host;','e.NeutralHost=Host;e.NeutralHost.panel=new v.Other;'),
    SOURCE.replace('3(m,e,r){const h=r(1)','3(m,e,r){const h=r(5)').replace('4(m,e,r){const h=r(1)','4(m,e,r){const h=r(5)').replace('e.Panel=Panel}}','e.Panel=Panel},5(m,e,r){class Other{}e.NeutralHost=Other}}'),
])
def test_rebound_panel_callback_or_unrelated_owner_never_supplies_signal(source):
    assert fixed_signal_command(source,ANSWER,_block) is None

def test_local_owner_alias_cannot_replace_the_active_panel_after_its_initial_binding():
    source=SOURCE.replace('e.NeutralHost=Host;','e.NeutralHost=Host;const Alias=Host;Alias.panel=new v.Other;')
    assert fixed_signal_command(source,ANSWER,_block) is None


def test_shared_automatic_planner_preserves_fixed_signal_payload():
    from tester_spin.providers.nolimit_city.client_actions import automatic_command
    assert automatic_command(SOURCE,ANSWER)=={'type':'zeroBet','bet':'0.00','playerInteraction':{'selectedIndex':'7'}}

@pytest.mark.parametrize('source',[
    SOURCE.replace('constructor(){this.button','constructor(){return;this.button'),
    SOURCE.replace('constructor(){this.button','constructor(){throw new Error("stop");this.button'),
    SOURCE.replace('constructor(){this.button','constructor(){if(this.blocked)return;this.button'),
    SOURCE.replace('constructor(){this.button','constructor(){if(false)this.button'),
])
def test_unreachable_or_conditionally_installed_button_never_supplies_signal(source):
    assert fixed_signal_command(source,ANSWER,_block) is None

def test_constructor_may_reach_a_button_through_direct_initialization_methods():
    source=SOURCE.replace('constructor(){this.button=new Button("signal",()=>this.clicked())}',
        'constructor(){this.init()}init(){this.createButton()}createButton(){this.button=new Button("signal",()=>this.clicked())}')
    assert fixed_signal_command(source,ANSWER,_block)['playerInteraction']=={'selectedIndex':'7'}
