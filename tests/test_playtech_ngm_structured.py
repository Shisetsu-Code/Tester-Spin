from test_playtech_ngm_contracts import CLIENT
from tester_spin.providers.playtech.ngm_observation import observation_points
from test_playtech_ngm_execution import apply,round_events

SOURCE=CLIENT+"""
function Bet(){}register(100,1,{100:1},Bet);var bt=type(ns,'CommonBet',100,parent);
function betWriter(req,out){var m,v;check(req,100);m=req;v=m.amount;v!=null&&put(out,'stake',number(v));v=m.kind;v!=null&&put(out,'type',text(v))}
function Request(){base.call(this,box(48000))}register(101,105,{101:1},Request);var start=type(ns,'FamilyStartSpinRequest',101,parent);
function writer(req,out){var m,v;check(req,101);m=req;v=m.bet;v!=null&&put(out,'bet',object(v));v=m.close;v!=null&&put(out,'closeAvailable',boolean(v))}
function sender(engine,bet,close){var q;q=new Request;q.bet=bet;q.close=close;transport(engine,q)}
function setStake(bet,value){bet.amount=value}
function entry(owner){var b;b=new Bet;b.kind='line';setStake(b,(calculate(owner)/100));sender(owner,b,false)}
"""


def test_nested_money_is_bound_through_serializer_producer_and_unit_conversion():
    from tester_spin.providers.playtech.ngm_structured import structured_spin_contract
    c=structured_spin_contract(SOURCE)
    assert c['constructor']=='Request'
    assert c['amount_field']=='amount' and c['type_field']=='kind'
    assert c['scale']==100 and c['bet_field']=='bet'
    assert c['sender']=='sender' and c['caller']=='entry'
    assert structured_spin_contract(SOURCE.replace("b.kind='line'","b.kind='purchase'")) is None
    assert structured_spin_contract(SOURCE.replace('/100','')) is None


def test_observation_normalizes_the_actual_entry_without_fabricating_coin_fields():
    source=SOURCE+'function dispatch(x,q){var out,h,v;out=new List;for(h=iter(q);h.more();){v=h.callback(q);append(out,v)}return out}'
    expression=observation_points(source)[0]['expression']
    assert 'structured-line' in expression and 'instanceof Request' in expression


def test_financial_ledger_accepts_declared_structured_entry_but_no_extra_entry():
    events=round_events();events[2]=('spin',{'bet':20,'wager_format':'structured-line','bet_type':'line'})
    assert apply(events).verified
    events.insert(6,events[2])
    assert not apply(events).verified


def test_sender_must_forward_money_unchanged():
    from tester_spin.providers.playtech.ngm_structured import structured_spin_contract
    for mutation in ("bet.kind='purchase';", "bet['pick']=selector;", 'mutate(bet);', "q.bet=bet;q.bet.kind='purchase';"):
        assert structured_spin_contract(SOURCE.replace('q.bet=bet;',mutation+'q.bet=bet;')) is None


def test_lifecycle_title_rejects_overrides():
    from tester_spin.providers.playtech.ngm_structured import _fixed_title
    row={'constructor':'R','fields':{'gameTitle':'title'}}
    for suffix in ("q.title='other';", "q['title']='other';"):
        assert _fixed_title({'send':([], 'q=new R;q.title=key;'+suffix)}, {'key':{'title'}}, row) is None
    assert _fixed_title({'send':([], 'q=new R;q.title=key;')}, {'key':{'title'}}, row)=='title'


def test_structured_entry_cannot_hide_an_active_classic_selector():
    from test_playtech_ngm_inventory import complete_har, LOADER
    from tester_spin.providers.playtech.ngm_contracts import analyze_har
    data=complete_har()
    data['log']['entries'][0]['response']['content']['text']=SOURCE+LOADER.replace("'regular',20,1", "'purchase',20,1")
    plan=analyze_har(data,'example')['execution_plan']
    assert not plan['complete']
    assert 'NGM_MULTIPLE_ENTRY_DOMAINS_UNBOUND' in plan['unresolved']


def test_additional_unbound_structured_producer_blocks_contract():
    from tester_spin.providers.playtech.ngm_structured import structured_spin_contract
    assert structured_spin_contract(SOURCE+'function buy(){var q;q=new Request;q.bet=makePurchaseBet();transport(q)}') is None


def test_returned_classic_request_cannot_escape_to_unbound_consumer():
    from test_playtech_ngm_inventory import complete_har, LOADER
    from tester_spin.providers.playtech.ngm_contracts import analyze_har
    data=complete_har()
    extra='function make(){var q;q=new Spin;return q}function buy(){var q;q=make();q.cost=100;transport(q)}'
    data['log']['entries'][0]['response']['content']['text']=SOURCE+LOADER.split('function sendSpin')[0]+extra
    plan=analyze_har(data,'example')['execution_plan']
    assert not plan['complete']
    assert 'NGM_MULTIPLE_ENTRY_DOMAINS_UNBOUND' in plan['unresolved']
