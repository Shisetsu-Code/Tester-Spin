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
