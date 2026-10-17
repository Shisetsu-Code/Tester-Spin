from tester_spin.providers.playtech.ngm_observation import observation_points

SOURCE = """
function dispatch(x,q){var out,h;out=new List;for(h=iter(q);h.more();){h.vf(q)}return out}
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
