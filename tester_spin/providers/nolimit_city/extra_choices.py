"""Client-declared numeric offers funded only by the pending round prize."""
import hashlib,re
from functools import lru_cache
from decimal import Decimal
from .protocol import _money
from .errors import Unlearned
from .operation_fields import step_win
from tester_spin.providers.repeat_purchase import funded_domain


def numeric_domain(source,game):
    if game.get('nextMode')!='EXTRA_SPIN':return None
    pattern=r'zeroBet\(\{playerSelectedExtraSpin:(0|1|"0"|"1"|\'0\'|\'1\')\}\)'
    literals=re.findall(pattern,source)
    numbers={int(v) for v in literals if len(v)==1}
    strings={v[1:-1] for v in literals if len(v)==3}
    if numbers=={0,1} and not strings:options=[0,1]
    elif strings=={'0','1'} and not numbers:options=['0','1']
    else:return None
    price=_money(game.get('extraSpinCost'),positive=True)
    accumulated=_money(game.get('accumulatedRoundWin'))
    target=game.get('nextModeForExtraSpin')
    if target is not None and target not in ('FREESPIN','SUPER_FREESPIN','FREESPIN_SUPER','FREESPIN_BETTER'):
        raise Unlearned('Nolimit City: destino del giro extra no declarado')
    domain={'state':'EXTRA_SPIN','options':options,'available':options,
        'request_field':'playerSelectedExtraSpin','wire_encoding':'PRESERVE_LITERAL',
        'ack_field':'numeric_extra_transition','source':'CLIENT_QUOTED_NUMERIC_EXTRA',
        'price_source':'game.extraSpinCost','quoted_price':str(price),
        'quoted_accumulated':str(accumulated),'target_phase':target}
    return funded_domain(domain,price,accumulated,accept=options[1],decline=options[0],funding_source='ACCUMULATED_ROUND_WIN')


def confirm_numeric(domain,selected,answer):
    game=answer.get('game') or {};accept=selected==domain['options'][1]
    price=_money(domain['quoted_price'],positive=True)
    if not any(type(selected) is type(value) and selected==value for value in domain['available']) or game.get('mode')!='EXTRA_SPIN' or _money(game.get('extraSpinCost'),positive=True)!=price:
        raise Unlearned('Nolimit City: giro extra sin precio o decisión confirmados')
    win=Decimal(str(step_win(game)))
    if accept:
        if (game.get('wasExtraSpin') is not True or game.get('nextMode') not in ('FREESPIN','SUPER_FREESPIN','FREESPIN_SUPER','FREESPIN_BETTER')
                or domain['target_phase'] is not None and game.get('nextMode')!=domain['target_phase']
                or type(game.get('freespinsLeft')) is not int or game['freespinsLeft']!=0 or win!=-price):
            raise Unlearned('Nolimit City: giro extra sin descuento o transición cotizados')
    elif game.get('wasExtraSpin') is not False or game.get('nextMode')!='NORMAL' or win!=0:
        raise Unlearned('Nolimit City: rechazo del giro extra sin liquidación confirmada')
    if 'isExtraSpin' in game and game['isExtraSpin'] is not accept:
        raise Unlearned('Nolimit City: indicadores de giro extra contradictorios')
    return -price if accept else Decimal(0)


@lru_cache(maxsize=8)
def _bound_returns(source):
    """Probe only static client phase references; the existing action prover decides."""
    from .client_actions import automatic_command
    from .protocol import MAX_BODY
    if not isinstance(source,str) or len(source)>MAX_BODY:return ()
    phase=r'[A-Z][A-Z0-9_]+'
    reference=r'(?:[\w]+\.[\w]+\.)?(["\']?'+phase+r'["\']?)'
    candidates=set()
    for pattern in (r'addGameModeFlowStatePresentationMap\('+reference,
                    r'nextMode=={1,2}'+reference,
                    r'\b('+phase+r'):\{idle:'):
        candidates.update(value.strip('"\'') for value in re.findall(pattern,source))
    # Enum properties can carry different wire values. Include the literal value;
    # automatic_command still requires the complete exact binding and call path.
    for key,value in re.findall(r'\b\w+\.('+phase+r')="('+phase+r')"',source):
        if key in candidates:candidates.add(value)
    result=[]
    for target in sorted(candidates-{'NORMAL','EXTRA_SPIN','EXTRA_SPIN_CHECK'}):
        for left in (0,1):
            view={'game':{'nextMode':target,'freespinsLeft':left}}
            if automatic_command(source,view)=={'type':'zeroBet','bet':'0.00'}:
                result.append((target,left))
    return tuple(result)


def literal_domain(source,game):
    """The yes/no dialect resumes the phase that advertised one extra spin."""
    if game.get('nextMode')!='EXTRA_SPIN':return None
    if not all(re.search(r'zeroBet\(\{playExtraSpin:["\']'+value+r'["\']\}\)',source) for value in ('yes','no')):return None
    price=_money(game.get('extraSpinCost'),positive=True);accumulated=_money(game.get('accumulatedRoundWin'))
    target=game.get('nextModeForExtraSpin',game.get('mode'))
    if not isinstance(target,str) or not re.fullmatch(r'[A-Z][A-Z0-9_]+',target) or target in ('NORMAL','EXTRA_SPIN','EXTRA_SPIN_CHECK'):
        raise Unlearned('Nolimit City: fase de retorno del giro extra no demostrada')
    if type(game.get('isExtraSpin')) is not bool:raise Unlearned('Nolimit City: indicador de giro extra no demostrado')
    bound_returns=_bound_returns(source)
    domain={'state':'EXTRA_SPIN','options':['no','yes'],'available':['no','yes'],
        'request_field':'playExtraSpin','wire_encoding':'PRESERVE_LITERAL',
        'ack_field':'quoted_literal_transition','source':'CLIENT_QUOTED_LITERAL_EXTRA',
        'price_source':'game.extraSpinCost','quoted_price':str(price),'quoted_accumulated':str(accumulated),
        'target_phase':target,'history_extra':game['isExtraSpin'],
        'quoted_target_phase':game.get('nextModeForExtraSpin')}
    if bound_returns:
        domain['allowed_return_states']=[{'phase':phase,'freespins_left':left} for phase,left in bound_returns]
        domain['return_binding_sha256']=hashlib.sha256(source.encode('utf-8')).hexdigest()
    return funded_domain(domain,price,accumulated,accept='yes',decline='no',funding_source='ACCUMULATED_ROUND_WIN')


def confirm_literal(domain,selected,answer):
    from .operation_fields import remaining_alias
    game=dict(answer.get('game') or {})
    if 'freespinsLeft' not in game and 'freespinsRemaining' in game:game['freespinsLeft']=remaining_alias(answer)
    price=_money(domain['quoted_price'],positive=True)
    if selected not in domain['available'] or game.get('mode')!='EXTRA_SPIN' or _money(game.get('extraSpinCost'),positive=True)!=price:
        raise Unlearned('Nolimit City: giro extra sin precio o decisión confirmados')
    win=Decimal(str(step_win(game)))
    if selected=='yes':
        quoted_target=domain.get('quoted_target_phase')
        if quoted_target is not None and game.get('nextMode')!=quoted_target:
            raise Unlearned('Nolimit City: retorno distinto del destino cotizado')
        allowed=domain.get('allowed_return_states')
        if allowed:
            target_ok=({'phase':game.get('nextMode'),'freespins_left':game.get('freespinsLeft')} in allowed
                and bool(domain.get('return_binding_sha256')))
            try:accumulated_ok=_money(game.get('accumulatedRoundWin'))==_money(domain['quoted_accumulated'])-price
            except ValueError:accumulated_ok=False
        else:
            target_ok=game.get('nextMode')==domain['target_phase'] and game.get('freespinsLeft')==1
            accumulated_ok=True
        if (game.get('isExtraSpin') is not True or not target_ok or not accumulated_ok
                or type(game.get('freespinsLeft')) is not int or win!=-price):
            raise Unlearned('Nolimit City: giro extra sin descuento o retorno a la fase que lo ofreció')
        return -price
    if (game.get('nextMode')!='NORMAL' or win!=0 or type(game.get('isExtraSpin')) is not bool
            or game['isExtraSpin'] is True and domain['history_extra'] is not True):
        raise Unlearned('Nolimit City: rechazo del giro extra sin liquidación o con historia incoherente')
    return Decimal(0)
