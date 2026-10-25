"""Current CommonAPI request, queued response and walking-symbol bindings.

The complete reviewed engine and extension bundles bind every private alias,
dispatcher and property write, in addition to matching the learned functions
in full. Only these protocol implementations are supported: any executable
revision requires review. Current server Config still supplies every price
and paytable; there is no game-ID or title match. CRLF is normalized to LF.
"""
import hashlib
import re

REVIEWED_SOURCE_SHA256 = '4b5fdf887e79d202a28fbc4509a13fb1134c3415e043b5fefe1ec72558ee5930'
REVIEWED_LOADER_SHA256 = '98658c469ef43e21894389d5189f6e7640c25f5d5e4b72e056ab53c4213f199d'


def loader_paths(source):
    """Resolve the reviewed sequential loader's own relative engine URLs."""
    if not isinstance(source, str) or hashlib.sha256(source.replace('\r\n', '\n').encode()).hexdigest() != REVIEWED_LOADER_SHA256:
        return None
    names = re.findall(r"src: launchParams\.gameBaseURL \+ 'engine-wrapper/' \+ launchParams\.provider \+ '/([^']+)'", source)
    if len(names) != 2 or not all(re.fullmatch(r'engine(?:-extensions)?\.[a-z0-9]+\.js', name) for name in names):
        return None
    return ['engine-wrapper/yggdrasil/' + name for name in names]

_FUNCTIONS = {'B=function()': 'return(parseInt(r.message_id)+1).toString()',
 'ee=function(e,n)': 'var t="string"==typeof e?parseFloat(e):e,r=o.Currency.getSubunits(n);return void '
                     '0===r?t:Math.round(t*Math.pow(10,r))',
 'ne=function(e,n)': 'var t="string"==typeof e?parseFloat(e):e,r=o.Currency.getSubunits(n);return void '
                     '0===r?t:parseFloat(t)/Math.pow(10,r)',
 'ce=function(e)': 'return e.reduce((function(e,n){return e+n.winnings}),0)',
 'de=function(e)': 'var n=["WINNING_LINES","WINNING_WAYS","WINNING_CLUSTERS"].reduce((function(n,t){return '
                   'e[t]&&e[t].length?n.concat(e[t]):n}),[]),t={},r=0;t.totalWinning=ce(n),t.betAmount=O().betAmount,t.winningList=n.map((function(e){return"Way"===e.winning_type&&(r+=e.source.aggregations),le[e.source.type].map(e)}));var '
                   'a=e.SCATTER&&e.SCATTER.length?e.SCATTER:[];t.totalWinning+=ce(a);var o=a.map((function(e){return '
                   'le[e.source.type].map(e)}));return t.winningList=t.winningList.concat(o),r>0&&(t.totalWays=r),t',
 'me=function(e)': 'var n={};return Object.keys(e).forEach((function(t){n[t]=e[t].reels})),n',
 'Ee=function(e)': 'var n=O(),t=e.data,r=t;U({betAmount:r.bet_amount}),O().slotMode===V&&(r=re(t));var '
                   'a={gameState:ae(r.state),nextEvent:o.GameActionTypes.SPIN,panel:r.panel.reels};n!==a.gameState&&(a.taxonomy=n.gameConfiguration.panelConfigurationPerState[a.gameState].taxonomy,a.paytable=n.gameConfiguration.panelConfigurationPerState[a.gameState].paytable,a.paylines=n.gameConfiguration.panelConfigurationPerState[a.gameState].paylines);var '
                   'i=function(e,n){return!fe(e)&&fe(n)?o.FeatureStates.ENTER:fe(e)&&fe(n)?o.FeatureStates.ACTIVE:fe(e)&&!fe(n)?o.FeatureStates.EXIT:o.FeatureStates.INACTIVE}(n.gameState,a.gameState),s=n.gameState;U(a);var '
                   'u={featureState:i,panelData:r.original_panel?r.original_panel.reels:[],gameState:a.gameState,configState:r.state,unprocessedParseData:{},winnings:de(r.winnings),scatterWinnings:ie(r.winnings),balance:n.balance,maxWinReached:r.max_win_reached,actionWinnings:r.action_winnings,roundWinnings:r.round_winnings,availableActions:[a.nextEvent],transforms:r.transforms,multiplier:r.counters.MULTIPLIER.value_per_bet[r.bet_amount]||1,freeRoundsData:n.freeRounds&&n.freeRounds.length?n.freeRounds[0]:null,previousPanelPerBet:r.previous_panel_per_bet?me(r.previous_panel_per_bet):null,transformSourcesPerBet:r.transform_sources_per_bet||null,special_reels:r.special_reels||[],special_reels_transforms:r.special_reels_transforms||[]};r.panel&&(u.newPanelData=r.panel.reels);var '
                   'l=ue(r.transforms);return '
                   'l.length&&(u.symbolOverrides=l),a.gameState===o.GameStates.RETRIGGERING&&(u.respinsData={context:{respinsAccumulatedWinnings:r.round_winnings}}),(ge.includes(a.gameState)||ge.includes(s))&&(u.freespinsData={context:{freeSpinsAccumulatedWinnings:r.round_winnings,freeSpinRemaining:ge.includes(a.gameState)?r.counters.FREE_SPINS.value_per_bet[r.bet_amount]:0}}),"<<<<< '
                   'Intercepting ".concat(e.type),u',
 'Te=function(e)': 'var n=O().buyBetAmounts;return Object.entries(e).map((function(e){var '
                   't=Pe(e,2),r=t[0];return{feature:r,price:t[1],availableBetsAmounts:n["BUY_".concat(r)]||n.BUY}}))',
 'Ye={trigger:function(e,n)': 'var '
                              't=O(),r=e.data.betAmount,a={type:g,message_id:B(),params:{action_type:f,bet_amount:r}},o=JSON.stringify(a),i={amount:ne(r,t.currencyCode),coin:ne(r/t.coinsPerBet,t.currencyCode),clientParams:o};return '
                              'n&&(i.test=!0,i.cheat="string"==typeof n||n instanceof '
                              'String?n:JSON.stringify(n)),w().spin(i)',
 'Ze={trigger:function(e)': 'var n=O(),t=e.data.id,r=e.data.betAmount,a=n.purchasableFeatures.find((function(e){return '
                            'e.feature===t}));if(!a)throw Error("Feature "+t+" is not purchasable");var '
                            'o=a.price,i={type:g,message_id:B(),params:{action_type:E,id:t,bet_amount:r}},s=JSON.stringify(i),u={cmd:n.purchasableFeatures.length>1?"BUY_"+t:"BUY",amount:parseFloat((ne(r,n.currencyCode)*o).toFixed(2)),coin:ne(r/n.coinsPerBet,n.currencyCode),clientParams:s};return '
                            'w().spin(u)',
 'Vn=function(e,n)': 'var t=e.map((function(e){var t=e,r=e.eventdata.response.clientData;return '
                     't.opensGameRound=r.data.opens_game_round,t.closesGameRound=r.data.closes_game_round,t.wager=n,t.spinEnded=!1,t}));Un=Un.concat(t)',
 'Yn=function()': 'return '
                  'w().getGameEventsEmitter().spinStarted().then((function(){return(Bn=Un.shift()).opensGameRound&&(Ln=!1),Ln=Ln||parseFloat(Bn.eventdata.accWa)>0,ke(Bn)}))',
 'e=function(L)': 'var '
                  'H=(L.special_reels||{SPECIAL_REEL:["1","5","10"]}).SPECIAL_REEL,n=L.counters.MULTIPLIERS_BOOSTERS,e=L.bet_amount;return{specialReels:H,multiplierBoosters:n.value_per_bet[e]||["BLANK, '
                  'BLANK"]}',
 'o=function(L)': 'return{respinMode:L.original_state.includes("RESPIN")?L.state.includes("RESPIN")?i:r:L.state.includes("RESPIN")?t:a}',
 'S=function(L)': 'var H=L.counters.COLLECTED_SCATTERS,n=L.bet_amount;return '
                  'H&&H.value_per_bet[n]?{scattersCollected:H.value_per_bet[n]}:{}',
 'C=function(L,H)': 'var '
                    'n=L.winnings,e=n.WILD_WINNINGS,t=n.WALKING_SYMBOLS_MULTIPLIER,r=L.transforms.WALKING_WILDS,i={};return '
                    'r&&r.length&&(i.walkingWilds=r.map((function(L){return '
                    'Object.assign({winnings:L.winnings,winIncluded:!1},L.transform.movements[0])}))),e&&e.length&&(i.wildCollectedWins=new '
                    'Array(3).fill(0),e.forEach((function(L){var '
                    'H=L.source.symbol.coordinates;i.wildCollectedWins[H.reel-1]+=L.winnings;var '
                    'n=i.walkingWilds.find((function(L){return '
                    'L.to&&L.to.reel===H.reel&&L.to.row===H.row}));n.winnings+=L.winnings,n.winIncluded=!0,n.currentWinnings=L.winnings}))),t&&t.length&&(i.wildWins=new '
                    'Array(5).fill(0),t.forEach((function(L){var '
                    'H=L.source.winning_symbols[0].coordinates,n=L.winnings,e=i.walkingWilds.find((function(L){return '
                    'null===L.to&&L.from.reel===H.reel&&L.from.row===H.row}));e.winnings=n,e.winIncluded=!0,i.wildWins[H.reel]=n}))),i',
 'I=function(L,H,n)': 'return '
                      'Object.assign(H,C(L.data,H)),Object.assign(H,e(L.data,H)),Object.assign(H,o(L.data,H)),Object.assign(H,S(L.data,H)),H',
 'u=function(L,H,n,t)': 'return '
                        'Object.values(H.gameConfiguration.panelConfigurationPerState).forEach((function(L){L.preCookedReels=l,L.taxonomy=3})),o(L.data.initial_state),Object.assign(H.initialData,e(L.data.initial_state)),H.initialData.panelData=H.initialData.panelData||s,H.gameConfiguration.scaler=10,H'}

def candidate(props):
    config = props.get('Config') if isinstance(props, dict) else None
    return (isinstance(config, dict) and config.get('is_persistent') is True
            and config.get('initial_state') == 'MAIN'
            and isinstance(config.get('per_state'), dict)
            and set(config['per_state']) == {'MAIN', 'MAIN_RESPIN', 'FREE_SPINS', 'FREE_SPINS_RESPIN'})


def declaration(props, source):
    if not candidate(props) or not isinstance(source, str):
        return None
    if hashlib.sha256(source.replace('\r\n', '\n').encode()).hexdigest() != REVIEWED_SOURCE_SHA256:
        return None
    for marker, body in _FUNCTIONS.items():
        # Include both braces: appended arithmetic and truncated initializer
        # matches are not proof of the renderer that produced this response.
        expression = marker + '{' + body + '}'
        if source.count(marker + '{') != 1 or source.count(expression) != 1:
            return None
    anchors = (
        'i="OpenGameResponse",s="GameActionResponse"',
        'g="GameActionRequest",f="SpinGameAction",E="BuyGameAction"',
        'On[o.GameActionTypes.SPIN]=Ye,On[o.GameActionTypes.BUY]=Ze,',
        'mt.registerHandler(i,Ge),mt.registerHandler(s,Ee),',
        'W.registerHandler("OpenGameResponse",u),W.registerHandler("GameActionResponse",I),',
        'a(r={AFN:2,EUR:2,ALL:2,',
    )
    if any(source.count(anchor) != 1 for anchor in anchors):
        return None
    config = props['Config']
    if config.get('special_bets_configuration') != {} or type(config.get('coins_per_bet')) is not int or config['coins_per_bet'] != 10:
        return None
    modes = props.get('Modes')
    buy = config.get('buy_configuration')
    if not isinstance(buy, dict) or len(buy) != 1 or not isinstance(modes, dict) or set(modes) != {'BASIC', 'BUY'}:
        return None
    purchase_id, multiplier = next(iter(buy.items()))
    if not isinstance(purchase_id, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}', purchase_id):
        return None
    if type(multiplier) is not int or not 1 < multiplier <= 10000:
        return None
    if modes['BASIC'] != {'coinsPerBet': 10} or modes['BUY'] != {'coinsPerBet': 10 * multiplier} or any(type(value.get('coinsPerBet')) is not int for value in modes.values()):
        return None
    awards = None
    for state in config['per_state'].values():
        if not isinstance(state, dict) or set(state) != {'prize_table', 'paylines', 'pre_cooked_reels'}:
            return None
        if state['paylines'] != [] or state['pre_cooked_reels'] != [[], [], [], [], []]:
            return None
        table = state['prize_table']
        if not isinstance(table, dict) or set(table) != {'symbol_prizes'} or not isinstance(table['symbol_prizes'], dict):
            return None
        if not table['symbol_prizes'] or any(not isinstance(key, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,31}', key) for key in table['symbol_prizes']):
            return None
        for row in table['symbol_prizes'].values():
            if not isinstance(row, dict) or set(row) != {'3', '4', '5'} or any(type(value) is not int or not 0 < value < 100000 for value in row.values()):
                return None
        if awards is not None and awards != table['symbol_prizes']:
            return None
        awards = table['symbol_prizes']
    if {'WI', 'SC'} & set(awards):
        return None
    return {'schema': 'common-action/walking-symbols-per-stake/v1',
            'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
            'source_binding': 'complete-reviewed-engine-and-extension-bundles/v1',
            'normalized_source_sha256': REVIEWED_SOURCE_SHA256,
            'height': 3, 'width': 5, 'bet_scaler': 10, 'currency': 'EUR', 'currency_decimal_places': 2,
            'coins_per_bet': 10, 'purchase_id': purchase_id, 'purchase_multiplier': multiplier,
            'awards': awards, 'wild': 'WI', 'wild_columns': [1, 2, 3], 'scatter': 'SC', 'states': list(config['per_state'])}
