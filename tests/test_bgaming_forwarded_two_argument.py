from tester_spin.providers.bgaming.hyperhive_wire import _has_req_bet_evidence
from tester_spin.providers.bgaming.hyperhive_contract_probe import _has_req_bet_type_evidence

SOURCE = """const rpc=async(method,params)=>{const response=await http.post("/api",{id:crypto.randomUUID(),jsonrpc:"2.0",method:method,params:params});if(response.data?.error)throw response.data.error;return response.data},play=async(req,lock)=>(await rpc("play",{token:token(),state_lock:lock,req:req})).result;
const build=()=>{const state=store.getState(),free=state.freebets;return{bet:free?limits[0]:state.bet,bet_type:free?"freebet":"bet"}};
async function resume(){const request=build(),response=await play(request,current.lock);return response}
"""

def test_two_argument_forwarder_proves_builder_request():
    assert _has_req_bet_evidence(SOURCE)
    assert _has_req_bet_type_evidence(SOURCE)


def test_two_argument_forwarder_rejects_unbound_or_changed_contract():
    for source in [SOURCE.replace('req:req}', 'req:other}'), SOURCE.replace('play(request,current.lock)', 'other(request,current.lock)'), SOURCE.replace('jsonrpc:"2.0"','protocol:"other"'), SOURCE.replace('request=build()', 'request=unrelated()'), SOURCE.replace('return{bet:', 'return{other:')]:
        assert not _has_req_bet_evidence(source)


def test_two_argument_forwarder_ignores_comments_strings_and_rebinding():
    import json
    for source in ['/*'+SOURCE+'*/', 'const docs='+json.dumps(SOURCE)+';', SOURCE+'play=async(req,lock)=>other(req);',SOURCE+'build=()=>({bet:0});']:
        assert not _has_req_bet_evidence(source)


def test_identical_collector_duplicates_preserve_proof():
    assert _has_req_bet_evidence(SOURCE + "\n" + SOURCE)


def test_shadowed_builder_or_wrapper_is_not_proof():
    assert not _has_req_bet_evidence(SOURCE + 'function other(play){play(request,current.lock)}')
    assert not _has_req_bet_evidence(SOURCE + 'function other(build){return build()}')
