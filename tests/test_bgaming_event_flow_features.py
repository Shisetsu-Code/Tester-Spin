"""Boolean purchase discriminator from bound UI events and a priced dispatch."""
import pytest

from test_bgaming_forwarded_feature_modes import purchases


SOURCE = '''const store=createStore(),bus=createEvents();
const buy=selection=>dispatch=>task(function*(){const{token:token}=store.getState().gameSlice,{wager:wager,index:index}=store.getState().spinSlice,subunits=store.getState().gameSlice.currencyAttributes.subunits,lock=store.getState().gameSlice.state_lock;const envelope={id:"fixture",jsonrpc:"2.0",method:"play",params:{req:{bet:Math.round(wager*subunits),bet_type:"betting",isSpecial:1!==selection,purchased_feature:"bonus_buy"},state_lock:lock,token:token}},request={method:"POST",headers:headers,body:JSON.stringify(envelope)};const reply=yield send(endpoint(),request,timeout);return reply});
class Popup{
subscribe(){this.view.first.on("pointerup",()=>{this.onYesClick(1)}),this.view.second.on("pointerup",()=>{this.onYesClick(2)})}
onYesClick(selection){this.canClick&&(bus.emit(events.APPLIED,selection),this.hide())}
}
class Game{
subscribe(){bus.on(events.APPLIED,this.handleBuy,this)}
handleBuy(selection){const{wager:wager}=store.getState().spinSlice,{balance:balance,isHistory:history}=store.getState().gameSlice,price=100*wager;this.ui.updateBalance(balance-price*selection),store.dispatch(buy(selection))}
}
// A separate base serializer already supported by the provider.
function base(){const req={bet:currentBet,bet_type:"betting"};return send({jsonrpc:"2.0",method:"play",params:{req:req}})}
'''


def test_boolean_variants_are_bound_to_two_ui_choices_and_explicit_debit():
    modes = purchases(SOURCE)
    assert {(m['request']['isSpecial'], m['expected_multiplier']) for m in modes} == {(False, 100), (True, 200)}
    assert all(m['request']['purchased_feature'] == 'bonus_buy' for m in modes)
    assert all(m['request']['bet_type'] == 'betting' for m in modes)
    assert all(m['coverage_required'] for m in modes)


@pytest.mark.parametrize('before,after', [
    ('isSpecial:1!==selection', 'isSpecial:1!==other'),
    ('bus.emit(events.APPLIED,selection)', 'bus.emit(events.OTHER,selection)'),
    ('bus.on(events.APPLIED,this.handleBuy,this)', 'other.on(events.APPLIED,this.handleBuy,this)'),
    ('store.dispatch(buy(selection))', 'store.dispatch(other(selection))'),
    ('store.dispatch(buy(selection))', 'store.dispatch(buy(other))'),
    ('balance-price*selection', 'balance-price'),
    ('price=100*wager', 'price=unknown*wager'),
    ('price=100*wager', 'price=-1*wager'),
    ('Math.round(wager*subunits)', 'Math.round(other*subunits)'),
    ('JSON.stringify(envelope)', 'JSON.stringify(other)'),
    ('method:"POST"', 'method:"GET"'),
    ('send(endpoint(),request,timeout)', 'send(endpoint(),other,timeout)'),
    ('this.onYesClick(2)', 'this.onYesClick(other)'),
    ('this.onYesClick(2)', 'this.onYesClick(2);this.onYesClick(3)'),
    ('{balance:balance,isHistory:history}=store.', '{balance:balance,isHistory:history}=other.'),
    ('onYesClick(selection){', 'onYesClick(selection){selection=other;'),
    ('const reply=yield', 'request.body="{}";const reply=yield'),
    ('request={method:"POST",headers:headers,', 'request={method:"POST",method:"GET",headers:headers,'),
    ('const reply=yield', 'const alias=request;alias.body="{}";const reply=yield'),
    ('const reply=yield', 'envelope.params.req.bet=1;const reply=yield'),
])
def test_broken_event_selector_price_or_transport_remains_unresolved(before, after):
    assert not purchases(SOURCE.replace(before, after))


def test_comments_and_rebinding_do_not_authorize_event_driven_purchases():
    assert not purchases('/*'+SOURCE+'*/')
    assert not purchases(SOURCE+'buy=other;')


def test_regex_arrow_body_cannot_hide_later_client_code():
    prefix = '''const accept=value=>/^[`"']$/i.test(value);'''
    assert len(purchases(prefix+SOURCE)) == 2
