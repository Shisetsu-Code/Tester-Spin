"""One state -> action -> acknowledgment -> money contract for live and HAR.

Captured requests are observations, never authority to invent a domain. Only
server state primitives and the exact current client's bindings authorize actions.
"""
import hashlib,re
from .errors import Unlearned
from .protocol import _money

SCHEMA='nolimit-city/operation-contract/v1'


def _contract(answer,family,source,*,request=None,domain=None,client_source=None):
    phase=(answer.get('game') or {}).get('nextMode')
    evidence={'source':source}
    if client_source is not None:evidence['client_sha256']=hashlib.sha256(client_source.encode('utf-8')).hexdigest()
    return {'schema':SCHEMA,'family':family,'state':phase,'request':request,'domain':domain,
        'acknowledgment':{'phase':phase,'kind':'PHASE_ENTRY'},
        'money':{'stake':'0.00','settlement':'ROUND_LEDGER','quote_field':domain.get('price_source') if domain else None},
        'evidence':evidence}


def resolve_operation(answer,mode=None,*,raw_answer=None,client_source=None):
    from .runtime import continuation,_extra_response
    from .client_actions import automatic_command
    from .choices import choice_domain,has_collect_contract
    from .operation_fields import collect_available
    mode=mode or {};raw=raw_answer if raw_answer is not None else answer
    try:
        request=continuation(answer,raw_answer=raw,
            declared_options=mode.get('declared_feature_options',()),declared_categories=mode.get('declared_feature_categories',()),
            declared_purchase_options=mode.get('declared_purchase_options',()),declared_catalog=mode.get('declared_feature_catalog'),
            declared_game_modes=mode.get('declared_game_modes',()))
        return _contract(raw,'AUTOMATIC_CONTINUATION','SERVER_STATE_PRIMITIVE',request=request)
    except Unlearned as blocker:
        if client_source is None:raise blocker
    automatic=automatic_command(client_source,raw)
    if automatic is not None:return _contract(raw,'AUTOMATIC_CONTINUATION','CURRENT_CLIENT_BINDING',request=automatic,client_source=client_source)
    game=raw.get('game') or {}
    if collect_available(game):
        if not has_collect_contract(client_source):raise Unlearned('Nolimit City: cobro no declarado por cliente')
        domain={'state':'GAMBLE','options':[True],'available':[True],'ack_field':'gambleCollect',
            'request_field':'gambleCollected','request_type':'gambleBet','source':'CLIENT_CONFIRMED_COLLECT','scope':'SETTLEMENT_ONLY'}
        family='COLLECT'
    elif _extra_response(game) and game.get('nextMode')=='EXTRA_SPIN':
        if not all(re.search(r'zeroBet\(\{playExtraSpin:[\"\']'+value+r'[\"\']\}\)',client_source) for value in ('yes','no')):
            raise Unlearned('Nolimit City: cliente no declara ambas decisiones del extra spin')
        price=_money(game.get('extraSpinCost'),positive=True)
        if _money(game.get('accumulatedRoundWin'))<price:raise Unlearned('Nolimit City: premio insuficiente para cubrir ambas decisiones del extra spin')
        domain={'state':'EXTRA_SPIN','options':['yes','no'],'available':['yes','no'],
            'ack_field':'extra_spin_transition','request_field':'playExtraSpin','price_source':'game.extraSpinCost'}
        family='QUOTED_EXTRA_SPIN'
    else:
        try:domain=choice_domain(client_source,raw)
        except ValueError as exc:raise Unlearned(str(exc)) from exc
        family='FINITE_SELECTION'
    return _contract(raw,family,domain['source'] if 'source' in domain else 'CURRENT_CLIENT_QUOTED_EXTRA',domain=domain,client_source=client_source)


def confirm_operation(contract,answer,selected=None):
    from .choices import confirm_choice
    game=answer.get('game') or {};phase=contract['acknowledgment']['phase']
    if game.get('mode')!=phase:raise Unlearned('Nolimit City: continuación sin acuse de la fase solicitada')
    domain=contract.get('domain')
    if domain is None:return
    field=domain.get('request_field','selectedIndex')
    if field=='gambleCollected':
        if game.get('nextMode')!='NORMAL' or game.get('gambleCollect') is not True:raise Unlearned('Nolimit City: cobro no confirmado')
    elif field=='playExtraSpin':
        if ((selected=='yes' and (game.get('nextMode')!='FREESPIN' or game.get('isExtraSpin') is not True))
                or (selected=='no' and game.get('nextMode')!='NORMAL')):raise Unlearned('Nolimit City: decisión extra spin no confirmada')
    else:confirm_choice(domain,selected,answer)


def observed_request_matches(contract,request):
    """Check an actual HAR request against authority; never learn its parameters."""
    if contract.get('request') is not None:return request==contract['request'],None
    domain=contract['domain'];field=domain.get('request_field','selectedIndex');interaction=request.get('playerInteraction')
    if (request.get('type')!=domain.get('request_type','zeroBet') or _money(request.get('bet'))!=0
            or not isinstance(interaction,dict) or set(interaction)!={field}):return False,None
    selected=next((v for v in domain['available'] if type(interaction[field]) is type(v) and interaction[field]==v
        or field=='selectedIndex' and interaction[field]==str(v)),None)
    return selected is not None,selected
