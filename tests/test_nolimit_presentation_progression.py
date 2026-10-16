import pytest
from tester_spin.providers.nolimit_city.client_actions import _block
from tester_spin.providers.nolimit_city.lifecycle import proves_zero_bet
from tester_spin.providers.nolimit_city.static_bindings import proves_bound_action

BASE='''{1(m,e,r){const p=r(2);e.Auto=class extends p.Base{shouldRun(){return!0}buildTimeline(){this.tl.add(()=>{game.apiPlugin.betHandler.zeroBet()})}}},2(m,e,r){e.Base=class{start(t){this.controller=t,this.tl=n.gsap.timeline({onComplete:()=>{t.setSkipCallback(),t.finish()},onStart:()=>{t.setSkipCallback(()=>{this.skip()})}}),this.buildTimeline()}skip(){this.tl.progress(1)}}},3(m,e,r){const a=r(1);new a.Auto}}'''

def test_bound_base_active_timeline_supports_direct_build_timeline_effect():
    assert proves_bound_action(BASE,BASE.index('new a.Auto'),'a.Auto',{'game':{}},_block)

@pytest.mark.parametrize('change',['paused','mutated','earlyreturn','payload'])
def test_direct_member_timeline_never_weakens_action_proof(change):
    source=BASE
    if change=='paused':source=source.replace('onComplete:','paused:!0,onComplete:')
    elif change=='mutated':source=source.replace('this.tl.add(()=>','this.tl.pause(),this.tl.add(()=>')
    elif change=='earlyreturn':source=source.replace('buildTimeline(){this.tl','buildTimeline(){return;this.tl')
    elif change=='payload':source=source.replace('zeroBet()','zeroBet({selectedIndex:choice})')
    assert not proves_bound_action(source,source.index('new a.Auto'),'a.Auto',{'game':{}},_block)

def test_playing_chained_timeline_declaration_preserves_later_root_callback():
    body='{start(){const tl=n.gsap.timeline().add(()=>ui.show()).add(()=>ui.fade());tl.add(()=>{api.betHandler.zeroBet()})}}'
    assert proves_zero_bet(body,_block)

@pytest.mark.parametrize('suffix',['.pause()','.timeScale(0)','.unknown()'])
def test_unknown_or_stopped_chained_timeline_cannot_authorize_action(suffix):
    body='{start(){const tl=n.gsap.timeline().add(()=>ui.show())'+suffix+';tl.add(()=>{api.betHandler.zeroBet()})}}'
    assert not proves_zero_bet(body,_block)

def test_bound_base_member_alias_preserves_one_playing_timeline():
    source=BASE.replace('buildTimeline(){this.tl.add','buildTimeline(){const tl=this.tl;tl.add')
    assert proves_bound_action(source,source.index('new a.Auto'),'a.Auto',{'game':{}},_block)

RUNNER='''{1(m,e,r){const i=r(2),a=r(3),run=r(4);e.Flow=class{constructor(){this.items=[new i.Intro,new a.Auto]}start(t){run.Runner.run(this.items,()=>t.finish(),s=>t.setSkipCallback(s))}}},2(m,e,r){const b=r(5),h=r(6);e.Intro=class extends b.Base{shouldRun(){return h.Host.model.intro}buildTimeline(){const tl=this.tl;tl.eventCallback("onComplete",()=>{this.controller.setSkipCallback()}),tl.add(()=>{h.Host.panel.enable(()=>this.continue())})}continue(){const tl=n.gsap.timeline().add(()=>ui.hide());tl.add(()=>{this.controller.finish()})}}},3(m,e,r){const b=r(5);e.Auto=class extends b.Base{shouldRun(){return!0}buildTimeline(){this.tl.add(()=>{api.betHandler.zeroBet()})}}},4(m,e,r){class R{static run(a,b,c){const d=a.concat(),f=d.shift();null==f?b():f.shouldRun()?f.start({finish:()=>R.run(d,b,c),setSkipCallback:c}):R.run(d,b,c)}}e.Runner=R},5(m,e,r){e.Base=class{start(t){this.controller=t,this.tl=n.gsap.timeline({onComplete:()=>{t.setSkipCallback(),t.finish()}}),this.buildTimeline()}skip(){this.tl.progress(1)}}},6(m,e,r){const p=r(7);class H{init(){H.panel=new p.Panel;}}e.Host=H},7(m,e,r){e.Panel=class{constructor(){this.button=new Button;this.button.addClickCallback(()=>this.clicked())}enable(cb){return n.gsap.timeline().add(()=>{this.callback=cb,this.button.enable(!0)})}clicked(){if(null==this.callback)throw new Error("no callback");this.callback(),delete this.callback}}},8(m,e,r){const f=r(1);new f.Flow}}'''

def test_proven_ui_completion_advances_the_runner_to_the_following_zero_bet():
    assert proves_bound_action(RUNNER,RUNNER.index('new f.Flow'),'f.Flow',{'game':{}},_block)

@pytest.mark.parametrize('change',['choice','introreturn','handlerpause','callbackargument','buttonreturn','arraymutation'])
def test_unknown_ui_or_choice_must_never_be_skipped_to_reach_later_zero_bet(change):
    source=RUNNER
    if change=='choice':source=source.replace('this.callback(),delete','api.betHandler.pickAndClickBet(choice,!1),this.callback(),delete')
    elif change=='introreturn':source=source.replace('buildTimeline(){const tl','buildTimeline(){return;const tl')
    elif change=='handlerpause':source=source.replace('tl.add(()=>{this.controller.finish()})','tl.pause(),tl.add(()=>{this.controller.finish()})')
    elif change=='callbackargument':source=source.replace('this.callback(),delete','this.callback(choice),delete')
    elif change=='buttonreturn':source=source.replace('constructor(){this.button','constructor(){return;this.button')
    elif change=='arraymutation':source=source.replace('this.items=[new i.Intro,new a.Auto]','this.items=[new i.Intro,new a.Auto],this.items.reverse()')
    assert not proves_bound_action(source,source.index('new f.Flow'),'f.Flow',{'game':{}},_block)

def test_timeline_identifier_shadowed_by_ui_arrow_parameter_is_not_an_escape():
    body='{start(){const tl=n.gsap.timeline();ui.items.filter(tl=>tl.visible);tl.add(()=>{api.betHandler.zeroBet()})}}'
    assert proves_zero_bet(body,_block)

def test_timeline_escape_outside_a_shadowing_arrow_still_blocks_action():
    body='{start(){const tl=n.gsap.timeline();ui.items.filter(tl=>tl.visible);unknown(tl);tl.add(()=>{api.betHandler.zeroBet()})}}'
    assert not proves_zero_bet(body,_block)

def test_chained_calls_on_a_known_timeline_keep_the_same_active_object():
    assert proves_zero_bet('{start(){const tl=n.gsap.timeline();tl.add(()=>ui.hide()).add(()=>ui.show());tl.add(()=>{api.betHandler.zeroBet()})}}',_block)

def test_bounded_for_let_iterator_in_ui_callback_does_not_mutate_timeline_alias():
    assert proves_zero_bet('{start(){const tl=n.gsap.timeline();tl.add(()=>{for(let tl=1;tl<=3;tl++)ui.sound(tl)});tl.add(()=>{api.betHandler.zeroBet()})}}',_block)

def test_continue_button_after_literal_ui_glyph_construction_is_reachable():
    source=RUNNER.replace('constructor(){this.button','constructor(){for(const ch of"012"){const glyph=new PIXI.BitmapText(ch,{fontName:fonts.Main,fontSize:100});glyph.position.x=this.label.width,this.label.addChild(glyph)}this.button')
    assert proves_bound_action(source,source.index('new f.Flow'),'f.Flow',{'game':{}},_block)
