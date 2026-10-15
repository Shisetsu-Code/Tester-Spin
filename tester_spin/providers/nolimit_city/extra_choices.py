"""Client-declared numeric offers funded only by the pending round prize."""
import re
from decimal import Decimal
from .protocol import _money
from .errors import Unlearned
from .operation_fields import step_win


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
    if accumulated<price:raise Unlearned('Nolimit City: premio insuficiente para cubrir ambas decisiones del giro extra')
    target=game.get('nextModeForExtraSpin')
    if target is not None and target not in ('FREESPIN','SUPER_FREESPIN','FREESPIN_SUPER','FREESPIN_BETTER'):
        raise Unlearned('Nolimit City: destino del giro extra no declarado')
    return {'state':'EXTRA_SPIN','options':options,'available':options,
        'request_field':'playerSelectedExtraSpin','wire_encoding':'PRESERVE_LITERAL',
        'ack_field':'numeric_extra_transition','source':'CLIENT_QUOTED_NUMERIC_EXTRA',
        'price_source':'game.extraSpinCost','quoted_price':str(price),
        'quoted_accumulated':str(accumulated),'target_phase':target}


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


def literal_domain(source,game):
    """The yes/no dialect resumes the phase that advertised one extra spin."""
    if game.get('nextMode')!='EXTRA_SPIN':return None
    if not all(re.search(r'zeroBet\(\{playExtraSpin:["\']'+value+r'["\']\}\)',source) for value in ('yes','no')):return None
    price=_money(game.get('extraSpinCost'),positive=True);accumulated=_money(game.get('accumulatedRoundWin'))
    if accumulated<price:raise Unlearned('Nolimit City: premio insuficiente para ambas decisiones del giro extra')
    target=game.get('nextModeForExtraSpin',game.get('mode'))
    if not isinstance(target,str) or not re.fullmatch(r'[A-Z][A-Z0-9_]+',target) or target in ('NORMAL','EXTRA_SPIN','EXTRA_SPIN_CHECK'):
        raise Unlearned('Nolimit City: fase de retorno del giro extra no demostrada')
    if type(game.get('isExtraSpin')) is not bool:raise Unlearned('Nolimit City: indicador de giro extra no demostrado')
    return {'state':'EXTRA_SPIN','options':['no','yes'],'available':['no','yes'],
        'request_field':'playExtraSpin','wire_encoding':'PRESERVE_LITERAL',
        'ack_field':'quoted_literal_transition','source':'CLIENT_QUOTED_LITERAL_EXTRA',
        'price_source':'game.extraSpinCost','quoted_price':str(price),'quoted_accumulated':str(accumulated),
        'target_phase':target,'history_extra':game['isExtraSpin']}


def confirm_literal(domain,selected,answer):
    game=answer.get('game') or {};price=_money(domain['quoted_price'],positive=True)
    if selected not in domain['available'] or game.get('mode')!='EXTRA_SPIN' or _money(game.get('extraSpinCost'),positive=True)!=price:
        raise Unlearned('Nolimit City: giro extra sin precio o decisión confirmados')
    win=Decimal(str(step_win(game)))
    if selected=='yes':
        if (game.get('isExtraSpin') is not True or game.get('nextMode')!=domain['target_phase']
                or type(game.get('freespinsLeft')) is not int or game['freespinsLeft']!=1 or win!=-price):
            raise Unlearned('Nolimit City: giro extra sin descuento o retorno a la fase que lo ofreció')
        return -price
    if (game.get('nextMode')!='NORMAL' or win!=0 or type(game.get('isExtraSpin')) is not bool
            or game['isExtraSpin'] is True and domain['history_extra'] is not True):
        raise Unlearned('Nolimit City: rechazo del giro extra sin liquidación o con historia incoherente')
    return Decimal(0)
