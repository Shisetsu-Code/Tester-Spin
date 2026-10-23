"""A replay-only payload must not hide the fresh demo's literal choice domain."""
import pytest
from tester_spin.providers.nolimit_city.extra_choices import numeric_domain


SOURCE='''({1(m,e,r){const p=r(2),b=r(6);class G extends b.Base{static init(){G.offer=new p.Panel}}e.Game=G},2(m,e,r){const g=r(1);class P{yes(){g.Game.apiPlugin.betHandler.zeroBet({playerSelectedExtraSpin:"1"})}no(){g.Game.apiPlugin.betHandler.zeroBet({playerSelectedExtraSpin:"0"})}history(x){const v=x.selected;g.Game.apiPlugin.betHandler.zeroBet({playerSelectedExtraSpin:v})}show(x){this.controller=x}}e.Panel=P},3(m,e,r){const g=r(1);class Idle{start(c){g.Game.apiPlugin.isReplay?g.Game.offer.history(c):g.Game.offer.show(c)}}e.Idle=Idle},4(m,e){class API{get isReplay(){return null!=this.options.replay}}e.API=API},6(m,e,r){const l=r(7),k=r(8);class Base{fetchPlugins(){for(let p of l.Launcher.plugins)(0,k.isApiPlugin)(p)&&(Base.apiPlugin=p);return Promise.resolve()}}e.Base=Base},7(m,e,r){const a=r(4);class Launcher{constructor(){Launcher.plugins=[],Launcher.apiPlugin=new a.API,Launcher.plugins.push(Launcher.apiPlugin)}}e.Launcher=Launcher},8(m,e){e.isApiPlugin=function(p){return void 0!==p.communication&&void 0!==p.slotStates}}})'''
OFFER={'mode':'EXTRA_SPIN_CHECK','nextMode':'EXTRA_SPIN','extraSpinCost':3,
       'accumulatedRoundWin':10,'wasExtraSpin':False,'nextModeForExtraSpin':'SUPER_FREESPIN'}


def test_only_source_bound_inactive_sdk_replay_method_is_excluded():
    assert numeric_domain(SOURCE,OFFER) is None
    domain=numeric_domain(SOURCE,OFFER,direct_demo_transport=True)
    assert domain is not None
    assert domain['options']==['0','1']
    assert domain['quoted_price']=='3'
    assert domain['live_selector_contract']=='nolimit-city/fresh-demo-selector/v1'
    assert len(domain['live_selector_binding_sha256'])==64


@pytest.mark.parametrize('before,after',[
    ('g.Game.apiPlugin.isReplay?','g.Game.model.isReplay?'),
    ('g.Game.apiPlugin.isReplay?','!g.Game.apiPlugin.isReplay?'),
    ('g.Game.apiPlugin.isReplay?','g.Game.apiPlugin.isReplay||other?'),
    ('g.Game.offer.history(c):g.Game.offer.show(c)',
     'g.Game.offer.show(c):g.Game.offer.history(c)'),
    ('start(c){','start(c){g.Game.offer.history(c);'),
    ('start(c){','start(c){const f=g.Game.offer.history;'),
    ('start(c){','start(c){const alias=g.Game.offer;alias.history(c);'),
    ('start(c){','start(c){g.Game.offer["history"](c);'),
    ('start(c){','start(c){g.Game.offer.history=unknown;'),
    ('start(c){','start(c){g.Game.offer=other;'),
    ('start(c){','start(c){g.Game.apiPlugin=other;'),
    ('show(x){','show(x){this.history(x);'),
    ('show(x){','show(x){this["history"](x);'),
    ('e.Panel=P','e.Panel=P;P.prototype.history=other'),
    ('e.Panel=P','e.Panel=P;P.prototype.history(other)'),
    ('G.offer=new p.Panel','G.offer=new p.Panel,G.second=new p.Panel'),
    ('return null!=this.options.replay','return this.options.replay||this.other'),
    ('e.Game=G','e.Game=G;G.offer=other'),
    ('static init(){','static get apiPlugin(){return other}static init(){'),
    ('start(c){','start(c){g.Game["offer"].history(c);'),
    ('start(c){','start(c){unknown(g.Game.offer);'),
    ('start(c){','start(c){const alias=g.Game.offer;unknown(alias);'),
    ('class G extends b.Base','class G'),
    ('Launcher.apiPlugin=new a.API','Launcher.apiPlugin=new a.Other'),
    ('Launcher.plugins.push(Launcher.apiPlugin)','Launcher.plugins.push(other)'),
    ('(0,k.isApiPlugin)(p)','(0,k.unrelated)(p)'),
    ('Base.apiPlugin=p','Base.apiPlugin=other'),
    ('e.Base=Base','e.Base=Base;Base.apiPlugin=other'),
    ('(0,k.isApiPlugin)(p)&&(Base.apiPlugin=p)',
     'flag&&((0,k.isApiPlugin)(p)&&(Base.apiPlugin=p))'),
    ('(0,k.isApiPlugin)(p)&&(Base.apiPlugin=p)',
     'p=other,(0,k.isApiPlugin)(p)&&(Base.apiPlugin=p)'),
    ('e.Launcher=Launcher','e.Launcher=Launcher;Launcher.plugins=other'),
])
def test_inactive_method_proof_rejects_other_reachable_or_mutable_paths(before,after):
    source=SOURCE.replace(before,after)
    assert numeric_domain(source,OFFER,direct_demo_transport=True) is None


def test_an_unrelated_unknown_payload_still_blocks_the_whole_domain():
    source=SOURCE.replace('show(x){','show(x){g.Game.apiPlugin.betHandler.zeroBet({playerSelectedExtraSpin:x});')
    assert numeric_domain(source,OFFER,direct_demo_transport=True) is None


@pytest.mark.parametrize('change', [
    'Launcher.plugins.push({communication:{},slotStates:{},isReplay:true})',
    'Launcher.plugins.push(other)',
    'Launcher.plugins[1]={communication:{},slotStates:{},isReplay:true}',
    'Launcher.plugins.push(new a.API(),unknown())',
    'Launcher.plugins.push(new a.API(unknown()))',
])
def test_another_api_plugin_cannot_supply_the_replay_guard(change):
    source=SOURCE.replace('Launcher.plugins.push(Launcher.apiPlugin)',
                          'Launcher.plugins.push(Launcher.apiPlugin),'+change)
    assert numeric_domain(source,OFFER,direct_demo_transport=True) is None


@pytest.mark.parametrize('change', [
    'g.Game.apiPlugin.options.replay="forced";',
    'const options=g.Game.apiPlugin.options;options.replay="forced";',
    'Object.assign(g.Game.apiPlugin.options,{replay:"forced"});',
])
def test_fresh_transport_does_not_allow_mutating_the_sdk_replay_options(change):
    source=SOURCE.replace('start(c){','start(c){'+change)
    assert numeric_domain(source,OFFER,direct_demo_transport=True) is None


@pytest.mark.parametrize('member', [
    'constructor(){this.options={replay:true}}',
    'constructor(){this.options=other}',
    'enable(){this.options.replay="forced"}',
    'enable(){const options=this.options;options.replay="forced"}',
    'enable(){Object.assign(this.options,{replay:true})}',
    'enable(){rewrite(this.options)}',
    'get options(){return {replay:true}}',
])
def test_sdk_getter_cannot_read_replaced_or_mutated_launch_options(member):
    source=SOURCE.replace('class API{','class API{'+member)
    assert numeric_domain(source,OFFER,direct_demo_transport=True) is None


def display_source():
    source=SOURCE.replace('const p=r(2),b=r(6);','const p=r(2),b=r(6),v=r(5);')
    source=source.replace('class G extends b.Base{static init(){G.offer=new p.Panel}',
        'class G extends b.Base{unused(){const v=other}static init(){G.offer=new p.Panel,v.View.addLayerAt(G.offer.name,G.offer,0)}')
    return source[:-2]+',5(m,e){class Display{static addLayerAt(n,v,i=0){Display._instance._layers[n]=v,v.name=n,Display._instance.stage.addChildAt(v,i),"Keypad"==n&&Display._instance._keypadLayer.addChildAt(v,i)}}e.View=Display}})'


def test_display_registration_can_only_insert_the_view_without_invoking_replay():
    source=display_source()
    assert numeric_domain(source,OFFER,direct_demo_transport=True)['options']==['0','1']
    assert numeric_domain(source.replace('v.name=n','v.history(n),v.name=n'),OFFER,direct_demo_transport=True) is None
    assert numeric_domain(source.replace('static init(){','static init(){const v=other;'),OFFER,direct_demo_transport=True) is None


@pytest.mark.parametrize('value',[False,1,'true',None])
def test_wire_or_truthy_values_cannot_supply_fresh_transport_context(value):
    assert numeric_domain(SOURCE,{**OFFER,'direct_demo_transport':True},direct_demo_transport=value) is None


# The SDK's real normalization chain, with independent module/class identifiers.
OPTIONS_NORMALIZER=r'''class U{static verifyOptions(e){if(!e||!e.game)throw new Error("Missing nolimit.options.game: "+JSON.stringify(e))}static getServerHost(e){if(e.serverHost)return e.serverHost.replace(/\/$/,"");const t=e.environment;return-1===t.indexOf(".")?"https://"+t+".nolimitcity.com":"https://"+t.replace("nolimitcdn","nolimitcity").replace("-us.nlccdn.com",".nlcus.com").replace("nlccdn","nlcgames").replace("nlcasiacdn","nlcasia")}static getOptions(e){return U.verifyOptions(e),e.device=e.device||"desktop",e.language&&(e.language=e.language.replace(/_/g,"-")),"verbose"!==e.language&&"succinct"!==e.language&&"zh-Hant"!==e.language&&"zh-hant"!==e.language&&"pt-BR"!==e.language&&"pt-br"!==e.language&&"us-sweepstakes"!==e.language&&"us-nonfree"!==e.language&&"de-x-sweep"!==e.language&&(e.language=(e.language||"en").substring(0,2).toLowerCase()),e.serverHost=U.getServerHost(e),!0!==e.hideCurrency&&"true"!==e.hideCurrency||(e.hideCurrency=!0),e.quality&&(e.quality=e.quality.toLowerCase()),e.smartLoading=e.smartLoading&&!1!==e.smartLoading,e.showDialogs=!1!==e.showDialogs,e.funMode=!e.token,e.realityCheck=e.realityCheck||{},e}}'''


def normalized_options_source():
    source=SOURCE.replace('4(m,e){class API{',
        '4(m,e,r){const u=r(9);class API{constructor(){this.options=u.Options.getOptions(window.nolimit.options),window.nolimit.options=this.options}')
    return source[:-2]+',9(m,e){'+OPTIONS_NORMALIZER+'e.Options=U}})'


def test_sdk_normalization_preserves_the_original_launch_replay_value():
    source=normalized_options_source()
    assert numeric_domain(source,OFFER,direct_demo_transport=True)['options']==['0','1']


@pytest.mark.parametrize('method',['getOptions','verifyOptions','getServerHost'])
@pytest.mark.parametrize('operation',[
    'window.nolimit.options.replay="forced";',
    'e.replay="forced";',
    'Object.assign(e,{replay:"forced"});',
    'rewrite(e);',
    'const saved=e;saved.replay="forced";',
    'e=other;',
])
def test_every_normalization_step_must_preserve_the_input_options(method,operation):
    source=normalized_options_source().replace('static '+method+'(e){',
        'static '+method+'(e){'+operation)
    assert numeric_domain(source,OFFER,direct_demo_transport=True) is None


@pytest.mark.parametrize('before,after',[
    ('e.realityCheck=e.realityCheck||{},e}', 'e.realityCheck=e.realityCheck||{},{replay:true}}'),
    ('U.verifyOptions(e),e.device', 'U.other(e),e.device'),
    ('e.serverHost=U.getServerHost(e)', 'e.serverHost=U.other(e)'),
    ('e.Options=U', 'e.Options=U;U.verifyOptions=other'),
    ('e.Options=U', 'e.Options=U;U.getServerHost=other'),
])
def test_normalization_returns_the_same_input_and_calls_bound_immutable_helpers(before,after):
    source=normalized_options_source().replace(before,after)
    assert numeric_domain(source,OFFER,direct_demo_transport=True) is None


@pytest.mark.parametrize('operation',[
    'window.nolimit.options.replay="forced";',
    'rewrite(window.nolimit.options);',
    'const saved=window.nolimit.options;saved.replay="forced";',
    'window.nolimit["options"].replay="forced";',
    'const root=window.nolimit;root.options.replay="forced";',
    'window["nolimit"].options.replay="forced";',
])
def test_published_launch_options_cannot_escape_to_an_unproved_consumer(operation):
    source=normalized_options_source().replace('start(c){','start(c){'+operation)
    assert numeric_domain(source,OFFER,direct_demo_transport=True) is None


@pytest.mark.parametrize('member',[
    'enable(){rewrite(window.nolimit.options=this.options)}',
    'enable(){const saved=window.nolimit.options=this.options;saved.replay="forced"}',
])
def test_publishing_options_cannot_itself_forward_the_assignment_result(member):
    source=normalized_options_source().replace('class API{','class API{'+member)
    assert numeric_domain(source,OFFER,direct_demo_transport=True) is None


ANALYTICS=r'''10(e){const t=["game","version","cdn","device","operator","currency","language","environment"];let i,n,o=!1;function s(e,t){o&&i.port1.postMessage({hitType:e,eventData:t})}const r={init:function(e){return void 0===n&&(!1===e.googleAnalytics?n=Promise.resolve():(r.options=function(e){const i={};return t.forEach(t=>{e[t]&&(i[t]=e[t])}),i}(e),n=new Promise((e,t)=>{i=new MessageChannel;const n=document.createElement("iframe");n.setAttribute("frameBorder","0"),n.style.width="0",n.style.height="0",n.id="nolimit-analytics",n.onload=function(){n.contentWindow.postMessage(JSON.stringify(r.options),r.options.cdn,[i.port2]),o=!0,e(n)},n.onerror=function(e){t(e.message)},n.src="{CDN}/analytics/analytics.html".replace("{CDN}",r.options.cdn).replace("{GAME}",r.options.game),document.body.appendChild(n)}))),n},screenView(e){o&&s("screenview",{screenName:e})},event(e,t,i){if(o){const n={eventCategory:r.options.game+"@"+r.options.device,eventAction:e};t&&("number"==typeof t?n.eventValue=t:n.eventLabel=String(t)),i&&(n.eventValue=i),s("event",n)}},exception(e,t){o&&s("exception",{exDescription:e,exFatal:t})},timing(e,t,i,n){if(o){const o={timingCategory:e,timingVar:t,timingValue:i};n&&(o.timingLabel=n),s("timing",o)}}};e.exports=r}'''


def analytics_options_source():
    source=normalized_options_source().replace('const u=r(9);','const u=r(9),q=r(10);')
    source=source.replace('window.nolimit.options=this.options}',
        'window.nolimit.options=this.options,q.init(this.options),this.analytics=q}')
    return source[:-2]+','+ANALYTICS+'})'


def test_analytics_receives_only_a_fresh_projection_of_declared_scalar_options():
    assert numeric_domain(analytics_options_source(),OFFER,direct_demo_transport=True)['options']==['0','1']


@pytest.mark.parametrize('before,after',[
    ('const t=["game","version","cdn","device","operator","currency","language","environment"]',
     'const t={forEach(f){f("__proto__").replay="forced"}}'),
    ('const t=["game","version","cdn","device","operator","currency","language","environment"]',
     'const t=unknown'),
    ('e.exports=r}', 'Object.assign(r,{init(e){e.replay="forced"}});e.exports=r}'),
    (',screenView(e){', ',get init(){return e=>{e.replay="forced"}},screenView(e){'),
    ('q=r(10);', 'q=r(10);q=other;'),
    ('q.init(this.options)', 'q.init=other,q.init(this.options)'),
    ('init:function(e){', 'init:function(e){e.replay="forced";'),
    ('i=new MessageChannel;', 'window.nolimit.options.replay="forced";i=new MessageChannel;'),
])
def test_analytics_projection_and_its_bound_consumer_cannot_be_replaced(before,after):
    source=analytics_options_source().replace(before,after)
    assert numeric_domain(source,OFFER,direct_demo_transport=True) is None
