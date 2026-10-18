from tester_spin.providers.playtech.client_sources import compiled_pick_binding

SOURCE="""
function sink(owner,id,params){var req={ID:id,parameters:JSON.parse(params)};GLU.game.playOut(owner,req)}
function send(owner,params){var out;sink(owner.x,owner.cmd,(out=new Output,copy(params,out),encode(out)))}
function copy(p,out){var key;key=p.key;write(out,"key",key);write(out,"value",p.value)}
function forward(owner,params,done){send(owner.inner,params)}
function pick(owner,value,done){var req;req=new Request;put(req.map,"pick",value);forward(owner,req,done)}
function put(map,key,value){map.data.set(key,void 0===value?null:value)}
function init(owner){owner.cmd=48775}
"""


def test_literal_pick_survives_forwarding_to_bound_continuation():
    assert compiled_pick_binding(SOURCE)


def test_literal_pick_requires_known_command_and_unmodified_forwarding():
    for old,new in [('48775','49999'),('"pick"','"mystery"'),('send(owner.inner,params)','send(owner.inner,mutate(params))')]:
        assert not compiled_pick_binding(SOURCE.replace(old,new))
