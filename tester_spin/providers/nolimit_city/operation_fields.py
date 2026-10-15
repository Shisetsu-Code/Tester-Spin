"""Monetary observations and root acknowledgments, independent of state catalogs."""
from decimal import Decimal,InvalidOperation

def step_win(game):
    names=[key for key in ('win','thisSpinWinning','thisSpinWinnings','thisAvalancheWinnings') if key in game]
    if not names:names=['totalSpinWinnings'] if 'totalSpinWinnings' in game else []
    if not names:raise ValueError('Nolimit City: premio de paso ausente')
    values=[]
    for key in names:
        value=game[key]
        if value is None or isinstance(value,bool):raise ValueError('Nolimit City: premio de paso inválido')
        try:number=Decimal(str(value))
        except InvalidOperation:raise ValueError('Nolimit City: premio de paso inválido') from None
        if not number.is_finite():raise ValueError('Nolimit City: premio de paso no finito')
        values.append(number)
    if len(set(values))!=1:raise ValueError('Nolimit City: premios de paso contradictorios')
    return game[names[0]]

def modifier_ack(game):
    flags=[]
    for key in ('wasBoostedBet','boostedBet','boostedBetPlayed','enhancedBet'):
        if key not in game:continue
        value=game[key]
        if type(value) is bool:flags.append(value)
        elif key=='enhancedBet' and type(value) is int and value>=0:flags.append(value>0)
        else:raise ValueError('Nolimit City: indicador de modificador inválido: '+key)
    if len(set(flags))>1:raise ValueError('Nolimit City: indicadores de modificador contradictorios')
    return flags[0] if flags else None

def root_ack(game,mode,request):
    kind=mode['kind'];purchase=game.get('wasFeatureBuy');boost=game.get('wasBoostedBet')
    if request is not None:
        expected='normalBet' if kind=='SPIN' else 'featureBet'
        if request.get('type')!=expected or Decimal(str(request.get('bet')))!=Decimal(str(mode['stake'])):
            raise ValueError('Nolimit City: petición raíz no coincide con la apuesta declarada')
        if kind=='SPIN' and set(request)!={'type','bet'}:
            raise ValueError('Nolimit City: parámetros inesperados en giro normal')
        if kind!='SPIN' and mode.get('selector') is not None:
            selector=mode['selector']
            if request.get('featureName')!=selector or request.get('playerInteraction')!={'featureName':selector}:
                raise ValueError('Nolimit City: petición raíz sin selector declarado')
    if purchase is not None and type(purchase) is not bool:raise ValueError('Nolimit City: acuse de compra inválido')
    if kind=='PURCHASE':
        if purchase is not True:raise ValueError('Nolimit City: compra no confirmada')
    elif kind=='FEATURE_SPIN':
        feature_ack=game.get('featureBet') is True and purchase is False
        if purchase is not False or (boost is not True and not (boost is None and feature_ack)):
            raise ValueError('Nolimit City: modificador no confirmado')
    else:
        if purchase is True or boost is True:raise ValueError('Nolimit City: giro normal con modificador inexplicado')
        if purchase is None or boost is None:
            if not isinstance(request,dict) or set(request)!={'type','bet'} or request.get('type')!='normalBet':
                raise ValueError('Nolimit City: giro normal sin petición y acuses contrastados')


def reconciled_step_win(game,previous):
    """Resolve a total-only dialect using both reported total and round accumulation."""
    total=step_win({'totalSpinWinnings':game.get('totalSpinWinnings')})
    accumulated=game.get('accumulatedRoundWin')
    if accumulated is None or isinstance(accumulated,bool):raise ValueError('Nolimit City: acumulado ausente o inválido')
    try:current=Decimal(str(accumulated));reported=Decimal(str(total));delta=current-previous
    except InvalidOperation:raise ValueError('Nolimit City: importes inválidos') from None
    if not current.is_finite() or not reported.is_finite() or current<0 or reported<0 or delta<0:
        raise ValueError('Nolimit City: total sin contrato de descuento')
    if reported not in (delta,current):raise ValueError('Nolimit City: total no concilia con paso ni acumulado')
    return str(delta)


def row_response(game):
    return (all(key in game for key in ('freespinPlayed','freespinsLeft','playedRowsInFS','playedRowsInBase','featureBuyRows','fsSpecialSymbol','wasFeatureBuy','freespinTriggeredThisSpin'))
        and type(game['freespinPlayed']) is int and game['freespinPlayed']>=0
        and type(game['freespinsLeft']) is int and game['freespinsLeft']>=0
        and all(type(game[k]) is int and 3<=game[k]<=5 for k in ('playedRowsInFS','playedRowsInBase'))
        and type(game['featureBuyRows']) is int and game['featureBuyRows'] in (-1,3,4,5)
        and isinstance(game['fsSpecialSymbol'],str)
        and all(type(game[k]) is bool for k in ('wasFeatureBuy','freespinTriggeredThisSpin')))


def collect_available(game):
    return (game.get('nextMode')=='GAMBLE' and type(game.get('gambleCollect')) is bool
        and game['gambleCollect'] is False and isinstance(game.get('gambleOptions'),dict))
