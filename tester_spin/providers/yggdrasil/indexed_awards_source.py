"""Bind safe acceptance, queued frames and counters to the current renderer."""
import hashlib
import re

from .sdk_purchase_list_roles import IDENT, SCOPE, methods, _method


def declaration(source):
    if not isinstance(source, str):
        return None
    owners = [owner for owner, _, body in methods(source, 'mapAdditionalSymbols') if '.outcome.reelLengthByIndex=' in body]
    if len(owners) != 1:
        return None
    owner = owners[0]
    parents = re.findall(re.escape(owner) + r'\.prototype=Object\.create\((' + SCOPE + r')\.prototype\)', source)
    if len(parents) != 1:
        return None
    parent = parents[0]
    for method in ('mapFeatures', 'mapFreeSpins', 'mapSingleFreeSpin', 'mapFreeSpinGamble'):
        if any(scope == owner for scope, _, _ in methods(source, method)):
            return None
    params, dispatch = _method(source, owner, 'mapAdditionalFeatures')
    if len(params) != 2:
        return None
    names = {}
    for name, method in [('gamble', 'mapFreeSpinGamble'), ('collector', 'mapFishermanFeature'), ('duplicate', 'mapDuplicateMultipliers'), ('hold', 'mapHoldAndWinFeature'), ('reset', 'mapResetLives')]:
        labels = re.findall(r'case"([^"\\]{1,64})":this\.' + method + r'\(' + re.escape(params[0]) + ',' + re.escape(params[1]) + r'\)(?:;break;|(?=\}$))', dispatch)
        if len(labels) != 1:
            return None
        names[name] = labels[0]
    types = re.findall(re.escape(parent) + r'\.prototype\.TYPES=\{([^}]{1,2000})\}', source)
    if len(types) != 1:
        return None
    for name, key in [('free', 'FREESPINS_NAME'), ('extra', 'FREESPINS_RETRIGGER_NAME2')]:
        values = re.findall(r'(?:^|,)' + key + r':"([^"\\]{1,64})"(?=,|$)', types[0])
        if len(values) != 1:
            return None
        names[name] = values[0]
    if len(set(names.values())) != len(names):
        return None
    params, body = _method(source, parent, 'mapFeatures')
    if len(params) != 2:
        return None
    call = params[0] + ',' + params[1]
    if body != 'switch(' + params[1] + '.bonusName){case this.TYPES.FREESPINS_NAME:this.mapFreeSpins(' + call + ');break;case this.TYPES.FREESPIN_SINGLE_NAME:this.mapSingleFreeSpin(' + call + ');break;case this.TYPES.FREESPINS_RETRIGGER_NAME:case this.TYPES.FREESPINS_RETRIGGER_NAME1:case this.TYPES.FREESPINS_RETRIGGER_NAME2:this.mapFreespinsRetrigger(' + call + ');break;default:this.mapAdditionalFeatures(' + call + ')}':
        return None
    params, body = _method(source, parent, 'mapFreeSpinGamble')
    if len(params) != 2:
        return None
    output, feature = params
    gamble = output + '.outcome.gamble'
    if body != gamble + '=' + gamble + '||{},' + ','.join(gamble + '.' + key + '=' + feature + '.' + key for key in ('currentFreeSpins', 'currentScatters', 'result', 'status')) + ',' + gamble + '.playerCanGamble="pending"===' + gamble + '.status':
        return None
    params, body = _method(source, parent, 'mapSingleFreeSpin')
    if len(params) != 2:
        return None
    output = params[0]
    single = (
        'this.freeSpins.end=!this.freespinResponse.length,this.freeSpins.active=!0,this.freeSpins.start=!1,'
        'this.freeSpins.total=this.totalFreeSpins,this.freeSpins.multiplier=this.multiplier,'
        'this.freeSpins.totalWin=(' + output + '.creditsWon||0)+' + output + '.creditsWonAccumulated+this.initialSpinWin,'
        + output + '.outcome.features=' + output + '.outcome.features||{},' + output + '.outcome.features.freespins=this.freeSpins,'
        + output + '.outcome.win=' + output + '.creditsWon||0'
    )
    if body != single:
        return None
    params, body = _method(source, owner, 'mapFishermanFeature')
    if len(params) != 2:
        return None
    output, feature = params
    if body != output + '.outcome.collectFishingTriggered=!0,this.collectFishingTriggered=!0,' + output + '.outcome.activeMultiplier=' + feature + '.multiplier,' + output + '.outcome.featureData={isFishCollected:!0,collectedPrice:' + feature + '.creditsWon},' + output + '.outcome.collectFishingTriggered&&(' + output + '.outcome.hasWins=!0)':
        return None
    params, body = _method(source, parent, 'mapFreeSpins')
    if len(params) != 2:
        return None
    local = re.match(r'var (' + IDENT + r');', body)
    if local is None:
        return None
    output, feature = params
    temporary = local[1]
    # The complete initializer binds the declared count to both counters. A
    # matching prefix must not hide arithmetic or a later counter overwrite.
    setup = (
        'var ' + temporary + ';' + output + '.outcome.win=(null==(' + temporary + '=' + output + '.winningLines)?void 0:' + temporary + '.creditsWon)||0,'
        'this.initialSpinWin=' + output + '.outcome.win,this.mapWins(' + output + ',' + feature + '),'
        'this.freespinResponse=angular.copy(' + feature + '.freeSpinList),this.totalFreeSpins=' + feature + '.count,'
        'this.freeSpins.name="fs",this.freeSpins.end=!1,this.freeSpins.active=!0,this.freeSpins.start=!0,'
        'this.freeSpins.total=this.totalFreeSpins,this.freeSpins.left=this.totalFreeSpins,this.freeSpins.count=this.totalFreeSpins,'
        'this.freeSpins.leftUpdate=this.freeSpins.left,this.freeSpins.totalWin=0+this.initialSpinWin,this.freeSpins.getTotalWin=this.getTotalWin,'
        + output + '.outcome.features=' + output + '.outcome.features||{},' + output + '.outcome.features.freespins=this.freeSpins,'
        + output + '.outcome.hasWins=!!' + output + '.outcome.win'
    )
    if body != setup:
        return None
    _, spin = _method(source, parent, 'spin')
    if 'this.freeSpins.leftUpdate--,this.freeSpins.left=this.freeSpins.leftUpdate' not in spin or 'this.processSpinResult(this.freespinResponse.shift())' not in spin:
        return None
    params, body = _method(source, owner, 'mapFreespinsRetrigger')
    extra = re.fullmatch(r'this\.freeSpins\.retrigger=!0,this\.freeSpins\.retriggerCount=([1-9][0-9]?),this\.freeSpins\.leftUpdate\+=\1', body)
    if extra is None:
        return None
    params, reset = _method(source, owner, 'mapResetLives')
    if len(params) != 1:
        return None
    life_match = re.fullmatch(re.escape(params[0]) + r'\.outcome\.resetLives=!0,' + re.escape(params[0]) + r'\.outcome\.respinLeft=([1-9][0-9]?)', reset)
    if life_match is None:
        return None
    lives = int(life_match[1])
    if len([body for _, _, body in methods(source, 'spin') if 'this.game.setRespinsLeft(this.scope.game.respinLeft-1)' in body]) != 1:
        return None
    params, hold = _method(source, owner, 'mapHoldAndWinFeature')
    if len(params) != 2:
        return None
    initial_lives = params[0] + '.outcome.respinLeft='
    hold_setup = initial_lives + str(lives) + ',' + params[1] + '.respinList&&(this.respinResponse=angular.copy(' + params[1] + '.respinList))'
    if hold.count(initial_lives) != 1 or not hold.endswith(',' + hold_setup):
        return None
    params, duplicate = _method(source, owner, 'mapDuplicateMultipliers')
    if len(params) != 2 or duplicate != params[0] + '.outcome.currentMultipliersAboveReels=' + params[1] + '.multipliers,' + params[0] + '.outcome.doubleMultiplierActive=!0':
        return None
    divisors = re.findall(r'this\.slot\.currentMultipliersAboveReels\.map\(function\((' + IDENT + r')\)\{return \1/([1-9][0-9]?)\}\)', source)
    if not divisors or len({value for _, value in divisors}) != 1:
        return None
    factor = int(divisors[0][1])
    if factor <= 1:
        return None
    # Incomplete columns retain a factor of one. A full treasure column uses
    # its current displayed multiplier; its money value is prize * base bet.
    treasury = []
    for _, _, body in methods(source, 'updateMoneyValue'):
        columns = re.search(r'this\.slot\.resultingReels\.forEach\(function\((' + IDENT + r'),(' + IDENT + r')\)\{-1==\1\.indexOf\(null\)\?this\.arr\[\2\]=this\.slot\.currentMultipliersAboveReels\[\2\]:this\.arr\[\2\]=1\}\.bind\(this\)\)', body)
        credit = re.search(r'\{setnumber:(' + IDENT + r')\.scope\.model\.prize\*\+this\.slot\.bet\*this\.arr\[\1\.scope\.model\.reelIndex\]\}', body)
        if credit is not None:
            value = re.escape(credit[1])
            update = re.search(value + r'\.scope\.model\.prize=' + value + r'\.scope\.model\.prize\*\+this\.slot\.bet\*this\.arr\[' + value + r'\.scope\.model\.reelIndex\]\)', body)
        else:
            update = None
        if columns and credit and update:
            treasury.append(body)
    if len(treasury) != 1:
        return None
    accepts = []
    for _, params, body in methods(source, 'getSpinRequestParams'):
        if len(params) != 1:
            continue
        amount = re.match(r'var (' + IDENT + r')=\{amount:this\.game\.getTotalBetInCash\(\),coin:this\.game\.getTotalBetInCash\(\)\};switch\(' + re.escape(params[0]) + r'\)', body)
        if amount is None:
            continue
        request = re.escape(amount[1])
        accept = re.search(r'case"freeSpinsEnter":' + request + r'\.cmd="([A-Z][A-Z0-9_]*)",' + request + r'\.type="bonus",' + request + r'\.step=this\.game\.getStep\(\)\+1,this\.manualCheatStack&&0<this\.manualCheatStack\.length&&\(' + request + r'\.cheat=this\.manualCheatStack\.shift\(\)\);break;', body)
        risk = re.search(r'case"gamble":' + request + r'\.cmd="([A-Z][A-Z0-9_]*)",' + request + r'\.type="bonus",' + request + r'\.step=this\.game\.getStep\(\)\+1,this\.gambleCheatStack&&0<this\.gambleCheatStack\.length&&\(' + request + r'\.cheat=this\.gambleCheatStack\.shift\(\)\);break;', body)
        if accept and risk and accept[1] != risk[1] and body.endswith('}return ' + amount[1]) and 'case"' + risk[1] + '":case"' + accept[1] + '"' in spin:
            accepts.append((accept[1], risk[1]))
    if len(accepts) != 1:
        return None
    return {'schema': 'indexed-output/current-safe-award-queue/v1', 'accept': accepts[0][0], 'risk': accepts[0][1], 'features': names, 'extra_spins': int(extra[1]), 'respin_lives': lives, 'duplicate_factor': factor, 'full_column_multipliers': True, 'source_sha256': hashlib.sha256(source.encode()).hexdigest()}
