from tester_spin.providers.playtech.ngm_observation import observation_points

SOURCE = """
function dispatch(x,q){var out,h,v;out=new List;for(h=iter(q);h.more();){v=h.vf(q);append(out,v)}return out}
function total(items){var sum,item,it;sum=0;for(it=new Iter(items);it.a<it.c.a.length;){item=next(it);sum+=item.f}return init(),sum<0?round(sum-0.5):round(sum+0.5)}
function credit(engine,items){var paid;paid=limit(global(),total(items));notify(engine.a,paid);return paid}
function result(engine,stops){var choices,paid,r;r=(choices=payouts(engine),paid=credit(engine,choices),new Result(engine,paid,choices));return r}
"""

def test_discovers_dispatch_and_calculated_payout_without_minified_names():
    points=observation_points(SOURCE)
    assert [p['type'] for p in points]==['offline.request','offline.response','offline.payout']
    payout=points[-1]
    assert payout['function']=='credit'
    assert payout['expression']=='({calculatedWin:paid})'
    assert SOURCE.splitlines()[payout['lineNumber']][payout['columnNumber']:].startswith('return paid')

def test_ambiguous_or_missing_math_does_not_certify_payout():
    assert not any(p['type']=='offline.payout' for p in observation_points(SOURCE.replace('sum+=item.f','sum+=unknown(item)')))
    duplicate=SOURCE+SOURCE[SOURCE.index('function result'):].replace('function result','function second').replace('credit(engine,choices)','other(engine,choices)')+'function other(engine,items){var paid;paid=limit(global(),total(items));notify(engine.a,paid);return paid}'
    assert not any(p['type']=='offline.payout' for p in observation_points(duplicate))

def test_unrelated_sum_and_credit_are_not_linked():
    assert not any(p['type']=='offline.payout' for p in observation_points(SOURCE.replace('paid=credit(engine,choices)','paid=unknown(engine,choices)')))


def test_offline_dispatcher_survives_minified_callback_renaming():
    renamed=SOURCE.replace('.vf(','.renamedCallback(')
    assert [p['type'] for p in observation_points(renamed)]==['offline.request','offline.response','offline.payout']


def test_event_binding_supports_start_without_confusing_stop():
    from tester_spin.providers.playtech.ngm_observation import event_action_binding
    source="function Start(){}register(7,1,{7:1},Start);var event=type(ns,'StartEvent',7,parent);function go(){send(new Start)}function send(e){bus(global,e)}"
    assert event_action_binding(source,'StartEvent')['constructor']=='Start'
    assert event_action_binding(source,'StopEvent') is None


def test_free_continuation_probes_follow_semantic_feature_and_active_control():
    from tester_spin.providers.playtech.ngm_observation import continuation_probes
    source="""
    var spinName='spin',freeName='free-spins';
    function Spin(){}register(10,1,{10:1},Spin);var req=type(ns,'SpinRequest',10,parent);
    function send(engine,phase){var q;q=new Spin;q.phase=phase;transport(engine,q)}
    function round(owner){send(owner.net,(same(feature(owner.features,null).id,freeName)?freeValue:normalValue))}
    function feature(manager,filter){var item,it;it=new Iter(manager.stack);while(it.more()){item=next(it);if(item.active){return item}}return null}
    function pending(manager){var item,it;for(it=new Iter(manager.stack);it.more();){item=next(it);return item}return null}
    register(20,1,{20:1},Buttons);_.init=function initialize(){prepare(this);write(this.model,spinName,null)};var typeName=type(ns,'DesktopRoundButtons',20,parent);
    function write(model,value,context){var previous;previous=model.current;model.set(value);if(!eq(previous,model.current)){notify(model)}}
    function setActive(buttons,value){write(buttons.model,value,null)}
    function current(buttons){return buttonById(buttons,buttons.model.current)}
    function buttonById(buttons,key){return lookup(buttons.buttons,key)}
    function style(){styleIt(this,this.disabledParent||this.disabledSelf?':disabled':'')}
    function available(){return this.visible&&!(this.disabledParent||this.disabledSelf)}
    """
    points=continuation_probes(source)
    assert {p['type'] for p in points}=={'feature','control'}
    assert any('feature(owner.features,null).id' in p['expression'] and 'pending(owner.features)' in p['expression'] for p in points)
    assert any('buttons.model' in p['expression'] and '.current' in p['expression'] and 'button.visible' in p['expression'] and 'available.call' not in p['expression'] for p in points)
    assert not continuation_probes(source.replace("spinName='spin'","spinName='unknown'"))
    assert not continuation_probes(source.replace('item=next(it);return item', 'item=next(it);if(item.filtered)continue;return item'))


def test_unhandled_dispatch_is_observed_at_early_return_without_guessing_effect():
    source="function dispatch(x,q){var out,h,v,handlers;out=new List;handlers=lookup(x.table,q.kind);if(!handlers)return out;for(h=iter(handlers);h.more();){v=h.callback(q);append(out,v)}return out}"
    points=observation_points(source)
    assert sum(p['type']=='offline.response' for p in points)==2
    request=next(p for p in points if p['type']=='offline.request')
    assert 'handlerAbsent:!handlers' in request['expression']
