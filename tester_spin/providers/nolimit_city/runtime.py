"""Fresh demo transport and money-checked primitives from the captured NLC SDK."""
from __future__ import annotations
import json,re,time,uuid
from decimal import Decimal,ROUND_HALF_UP
from select import select
from curl_cffi import CurlError
from curl_cffi.const import CurlECode,CurlInfo,CurlWsFlag
from .protocol import rc4_hex,lzw_decode,websocket_url,_money,_closed,MAX_BODY

API='https://demo.nolimitcity.com/EjsFrontWeb/fs'
CDN='https://demo.nolimitcdn.com/games/'
PROTOCOL='@nolimitcity/game-communication@0.4.1'
MONETARY='nolimit-city/round-ledger/v1'

class Unlearned(ValueError):
    """A current server state has no demonstrated execution primitive."""

def save(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def sanitized(data):
    if isinstance(data,list):return [sanitized(v) for v in data]
    if isinstance(data,dict):return {k:sanitized(v) for k,v in data.items() if k not in {'extPlayerKey','playerConnect','key','token','tokenString'}}
    return data

class NolimitSession:
    def __init__(self):
        self.socket=None;self.rows=[];self.capture=None;self.remembered={};self.counter=0;self.uuid=uuid.uuid4().hex;self.choice_domains={};self.pending_choice=None;self.choice_client=None
    def open(self,game,http,timeout,stop,directory):
        self.timeout=max(.1,float(timeout));self.stop=stop
        response=http.get(CDN+game.symbol+'/info.json',timeout=self.timeout);response.raise_for_status()
        info=response.json();version=info.get('version')
        if info.get('name')!=game.symbol or not isinstance(version,str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',version):
            raise Unlearned('Nolimit City: identidad o versión de cliente desconocida')
        self.client_info=info;self.http=http;self.choice_root=directory
        save(directory/'client-info.json',info)
        payload={'action':'open_game','clientString':'FANPAGE_DEMO','language':'en','gameCodeString':game.symbol+'@desktop'}
        save(directory/'bootstrap-request.json',payload)
        response=http.post(API,data=payload,headers={'Origin':'https://playin.com'},timeout=self.timeout);response.raise_for_status()
        config=response.json()
        if not isinstance(config,dict) or not isinstance(config.get('key'),str):raise Unlearned('Nolimit City: servidor no abrió la Demo')
        self.key=config['key'];target=websocket_url(config.get('url',''),self.key)
        self.target=target
        self.capture={'log':{'version':'1.2','creator':{'name':'Tester-Spin','version':'nolimit-runtime-v1'},
            'entries':[{'request':{'method':'POST','url':API,'postData':{'mimeType':'application/x-www-form-urlencoded','text':'&'.join(k+'='+v for k,v in payload.items())}},
                'response':{'status':response.status_code,'content':{'mimeType':'application/json','text':json.dumps(config)}}}],
            '_warpWebSockets':self.rows}}
        self.capture_path=directory.parent/'capture.har'
        self.socket=http.ws_connect(target,headers={'Origin':'https://playin.com'},timeout=self.timeout)
        reply=self._exchange({'type':'init'},directory,version=version)
        if reply.get('init')!='ok':raise Unlearned('Nolimit City: inicialización no confirmada')
        return reply
    def _receive(self):
        deadline=time.monotonic()+self.timeout;parts=[];size=0
        while time.monotonic()<deadline:
            if self.stop.is_set():raise Unlearned('Nolimit City: ejecución detenida')
            try:
                chunk,frame=self.socket.recv_fragment()
            except CurlError as exc:
                if exc.code!=CurlECode.AGAIN:raise
                select([self.socket.curl.getinfo(CurlInfo.ACTIVESOCKET)],[],[],min(.1,max(0,deadline-time.monotonic())))
                continue
            if frame.flags & CurlWsFlag.CLOSE:raise Unlearned('Nolimit City: servidor cerró la conexión')
            if frame.flags & (CurlWsFlag.PING|CurlWsFlag.PONG):continue
            size+=len(chunk)
            if size>MAX_BODY:raise Unlearned('Nolimit City: respuesta excede el límite')
            parts.append(chunk)
            if frame.bytesleft==0 and not frame.flags & CurlWsFlag.CONT:
                if not frame.flags & CurlWsFlag.TEXT:raise Unlearned('Nolimit City: trama de formato desconocido')
                return b''.join(parts).decode('utf-8')
        raise TimeoutError('Nolimit City: tiempo de respuesta agotado; no se reenvía una apuesta incierta')
    def _exchange(self,content,directory,version=None):
        if self.stop.is_set():raise Unlearned('Nolimit City: ejecución detenida')
        self.counter+=1
        request={'type':'init' if version else 'normal','content':content,'protocol':PROTOCOL,
                 'id':self.uuid+'-'+str(self.counter),'data':self.remembered.copy()}
        if version:request['gameClientVersion']=version
        save(directory/f'{self.counter:04d}.request.json',sanitized(request))
        plaintext=json.dumps(request,separators=(',',':'),ensure_ascii=True)
        encrypted=rc4_hex(self.key,plaintext.encode('latin1').hex()).encode('latin1').hex()
        self.rows.append({'url':self.target,'direction':'sent','timestamp':time.time(),'payload':encrypted,'encoding':'utf8'})
        self.socket.send(encrypted,flags=CurlWsFlag.TEXT)
        raw=self._receive()
        self.rows.append({'url':self.target,'direction':'received','timestamp':time.time(),'payload':raw,'encoding':'utf8'})
        answer=json.loads(lzw_decode(raw))
        save(directory/f'{self.counter:04d}.response.json',sanitized(answer))
        if not isinstance(answer,dict) or answer.get('id')!=request['id']:raise Unlearned('Nolimit City: respuesta no corresponde a la petición')
        if answer.get('error'):raise Unlearned('Nolimit City: servidor rechazó la operación')
        ext=answer.get('extPlayerKey')
        if ext is not None:
            if not isinstance(ext,str) or not ext:raise Unlearned('Nolimit City: continuidad de sesión inválida')
            self.remembered={'extPlayerKey':ext}
        return answer
    def exchange(self,content,directory):return self._exchange(content,directory)
    def choice_command(self,answer,directory,root_id):
        from .choices import choice_domain,has_collect_contract
        if self.choice_client is None:
            info=self.client_info
            target=CDN+info['name']+'/'+info['version']+'/game.js'
            response=self.http.get(target,timeout=self.timeout);response.raise_for_status()
            if len(response.content)>MAX_BODY:raise Unlearned('Nolimit City: cliente excede el límite de descubrimiento')
            self.choice_client=response.text
        game=answer.get('game') or {}
        if _row_response(game) and game.get('nextMode')=='GAMBLE':
            if not has_collect_contract(self.choice_client):
                raise Unlearned('Nolimit City: cobro no declarado por cliente')
            domain={'state':'GAMBLE','options':[True],'available':[True],'ack_field':'gambleCollect',
                'request_field':'gambleCollected','request_type':'gambleBet','source':'CLIENT_CONFIRMED_COLLECT','scope':'SETTLEMENT_ONLY'}
        elif _extra_response(game) and game.get('nextMode')=='EXTRA_SPIN':
            if not all(re.search(r'zeroBet\(\{playExtraSpin:[\"\']'+value+r'[\"\']\}\)',self.choice_client) for value in ('yes','no')):
                raise Unlearned('Nolimit City: cliente no declara ambas decisiones del extra spin')
            price=_money(game.get('extraSpinCost'),positive=True)
            if _money(game.get('accumulatedRoundWin'))<price:
                raise Unlearned('Nolimit City: premio insuficiente para cubrir ambas decisiones del extra spin')
            domain={'state':'EXTRA_SPIN','options':['yes','no'],'available':['yes','no'],
                'ack_field':'extra_spin_transition','request_field':'playExtraSpin','price_source':'game.extraSpinCost'}
        else:
            try:domain=choice_domain(self.choice_client,answer)
            except ValueError as exc:raise Unlearned(str(exc)) from exc
        key=(root_id,domain['state']);known=self.choice_domains.get(key)
        if known is None:
            known={**domain,'covered':[]};self.choice_domains[key]=known
        elif known['options']!=domain['options'] or known['ack_field']!=domain['ack_field']:
            raise Unlearned('Nolimit City: dominio de elección cambió durante la prueba')
        selected=next((option for option in domain['available'] if option not in known['covered']),domain['available'][0])
        self.pending_choice=(domain,selected,key)
        save(directory/'choice-domain.json',{**domain,'selected':selected,'root_mode':root_id})
        return {'type':domain.get('request_type','zeroBet'),'bet':'0.00','playerInteraction':{domain.get('request_field','selectedIndex'):selected if domain.get('request_field')=='gambleCollected' else str(selected)}}
    def confirm_pending_choice(self,answer):
        if self.pending_choice is None:return
        from .choices import confirm_choice
        domain,selected,key=self.pending_choice
        if domain.get('request_field')=='gambleCollected':
            game=answer.get('game') or {}
            if game.get('mode')!='GAMBLE' or game.get('nextMode')!='NORMAL' or game.get('gambleCollect') is not True:
                raise Unlearned('Nolimit City: cobro no confirmado')
        elif domain.get('request_field')=='playExtraSpin':
            game=answer.get('game') or {}
            if game.get('mode')!='EXTRA_SPIN' or (selected=='yes' and (game.get('nextMode')!='FREESPIN' or game.get('isExtraSpin') is not True)) or (selected=='no' and game.get('nextMode')!='NORMAL'):
                raise Unlearned('Nolimit City: decisión extra spin no confirmada')
        else:confirm_choice(domain,selected,answer)
        covered=self.choice_domains[key]['covered']
        if selected not in covered:covered.append(selected)
        self.pending_choice=None
    def sync_choices(self,mode):
        mode['choice_domains']=[{k:v for k,v in domain.items() if k not in ('available','before')}
            for (root_id,state),domain in self.choice_domains.items() if root_id==mode['id']]
        return all(set(domain['options'])<=set(domain['covered']) for domain in mode['choice_domains'])
    def close(self):
        if self.capture is not None:save(self.capture_path,self.capture)
        if self.socket is not None:
            try:self.socket.close()
            except Exception:pass

def _boosted_response(game):
    return (all(key in game for key in ('boostedBet','wasFeatureBuy','playedBetValue',
        'accumulatedRoundWin','mode','nextMode','freespinsLeft','freespinsPlayed'))
        and ('win' in game or 'totalSpinWinnings' in game))


def _row_response(game):
    return (all(key in game for key in ('freespinPlayed','freespinsLeft','playedRowsInFS','playedRowsInBase','featureBuyRows','fsSpecialSymbol','wasFeatureBuy','freespinTriggeredThisSpin'))
        and type(game['freespinPlayed']) is int and game['freespinPlayed']>=0
        and type(game['freespinsLeft']) is int and game['freespinsLeft']>=0
        and all(type(game[k]) is int and 3<=game[k]<=5 for k in ('playedRowsInFS','playedRowsInBase'))
        and type(game['featureBuyRows']) is int and game['featureBuyRows'] in (-1,3,4,5)
        and isinstance(game['fsSpecialSymbol'],str)
        and all(type(game[k]) is bool for k in ('wasFeatureBuy','freespinTriggeredThisSpin')))

def _level_response(game):
    fields=('totalSpinWinnings','accumulatedRoundWin','playedBetValue','mode','nextMode',
        'numberOfFreespinsPlayed','freespinsLeft','freespinTriggeredThisSpin','wasFeatureBuy',
        'collapsedReel','collectedWinningSymbols','previousLevel','currentLevel','isRandomLevel')
    return (all(key in game for key in fields) and isinstance(game['collapsedReel'],list)
        and all(type(game[key]) is bool for key in ('freespinTriggeredThisSpin','wasFeatureBuy','isRandomLevel'))
        and all(type(game[key]) is int and game[key]>=0 for key in ('numberOfFreespinsPlayed','freespinsLeft','collectedWinningSymbols','previousLevel','currentLevel'))
        and not any(key in game for key in ('boostedBet','boostedBetPlayed','enhancedBet','extraSpinCost','isExtraSpin')))

def _extra_response(game):
    return (_boosted_response(game) and type(game.get('isExtraSpin')) is bool
        and type(game.get('isSuperFreespins')) is bool)

def _category_response(game):
    return (all(key in game for key in ('featureBet','numberOfFreespinsPlayed',
        'totalSpinWinnings','freespinTriggeredThisSpin','wasFeatureBuy','playedBetValue',
        'accumulatedRoundWin','mode','nextMode','freespinsLeft'))
        and (game['featureBet'] is False or (game['featureBet'] is True and game['wasFeatureBuy'] is True
            and game['mode']=='NORMAL' and game['numberOfFreespinsPlayed']==0)))


def _batch_response(game):
    core=all(key in game for key in ('wasFeatureBuy','playedBetValue','accumulatedRoundWin',
        'totalSpinWinnings','mode','nextMode','freespinsLeft'))
    counter=any(type(game.get(key)) is int and game[key]>=0
        for key in ('freespinsPlayed','freeSpinsPlayed','numberOfFreespinsPlayed'))
    marker=any(type(game.get(key)) is bool for key in ('boostedBet','boostedBetPlayed','enhancedBet'))
    numeric_enhanced=type(game.get('enhancedBet')) is int and game['enhancedBet']>=0
    return core and counter and (marker or numeric_enhanced)


def _pending_auto_phase(answer,game,*,explicit_no_extra=False):
    next_mode=game.get('nextMode');left=game.get('freespinsLeft')
    if (_category_response(game) and next_mode=='STACKED_RESPIN_FREESPIN'
            and answer.get('pendingWin') is True and game.get('stackedSpinTriggered') is True
            and type(left) is int and left>0):return True
    if (_level_response(game) and next_mode in ('AVALANCHE_NORMAL','AVALANCHE_FREESPIN','AVALANCHE_FREESPIN_SUPER')
            and answer.get('pendingWin') is True and game['collapsedReel'] and _money(game.get('win'))>0):return True
    if not _batch_response(game):return False
    state_shape=any(isinstance(game.get(key),list) and game[key]
        for key in ('reelsAfterCollapse','reelsAfterAvalanche','symbolsAfterTumbleForClient'))
    respins={'NORMAL_AVALANCHE_RESPIN','FREESPIN_AVALANCHE_RESPIN','SUPER_FREESPIN_AVALANCHE_RESPIN'}
    if next_mode in respins and state_shape and explicit_no_extra and game.get('wasExtraSpin') is False:
        return _money(game.get('extraSpinCost'))==0
    avalanche=next_mode in {'NORMAL_AVALANCHE','FREESPIN_AVALANCHE','SUPER_FREESPIN_AVALANCHE'}
    return bool(answer.get('pendingWin') is True and avalanche and state_shape and _money(game.get('win'))>0)


def require_idle_initial_state(init):
    game=init.get('game') or {};available=(init.get('features') or {}).get('available',[])
    idle=(game.get('nextMode')=='NORMAL' and type(game.get('freespinsLeft')) is int
        and game['freespinsLeft']==0 and init.get('remainingFreeSpins')==0)
    advertised=init.get('allowedFeatureBets') or []
    exact_catalog=(isinstance(available,list) and available and len(available)==len(set(available))
        and set(available)==set(advertised))
    category_catalog=((available==['FREESPINS'] or exact_catalog) and game.get('isRestoreState') is False
        and game.get('mode')=='NORMAL' and type(game.get('numberOfFreespinsPlayed')) is int
        and game['numberOfFreespinsPlayed']==0 and game.get('freespinTriggeredThisSpin') is False
        and game.get('wasFeatureBuy') is False)
    row_catalog=(_row_response(game) and available==['FREESPIN'] and game.get('isRestoreState') is False
        and game.get('mode')=='NORMAL' and game['freespinPlayed']==0 and game['wasFeatureBuy'] is False
        and game['freespinTriggeredThisSpin'] is False)
    if not idle or (available!=[] and not category_catalog and not row_catalog):
        raise Unlearned('Nolimit City: estado inicial sin primitiva aprendida; opciones declaradas conservadas')


def declaration(init, *, require_idle=True):
    game=init.get('game');config=init.get('gameClientConfiguration');allowed=init.get('allowedFeatureBets')
    levels=init.get('featureBetLevels');types=init.get('allowedFeatureTypes')
    if not isinstance(game,dict) or not isinstance(config,dict) or not isinstance(levels,dict) or not isinstance(types,list):
        raise Unlearned('Nolimit City: declaración incompleta de opciones y apuestas')
    table=game.get('featureBuyTimesBetValue')
    if table is None and allowed==[]:table=[]
    if not isinstance(table,list) or not isinstance(allowed,list) or any(not isinstance(v,str) or not v for v in allowed) or len(set(allowed))!=len(allowed):
        raise Unlearned('Nolimit City: dominio de opciones ausente o inválido')
    quotes={}
    for item in table:
        if not isinstance(item,dict) or not isinstance(item.get('name'),str) or not item['name'] or item['name'] in quotes:
            raise Unlearned('Nolimit City: precio duplicado o inválido')
        quotes[item['name']]=item
    if set(allowed)-set(quotes):raise Unlearned('Nolimit City: selector permitido sin precio')
    base=(init.get('betLevels') or {}).get('availableBetLevels')
    if not isinstance(base,list) or not base:raise Unlearned('Nolimit City: dominio de apuesta normal ausente')
    stake=min(_money(v,positive=True) for v in base)
    if stake!=stake.quantize(Decimal('.01')):raise Unlearned('Nolimit City: escala de apuesta no demostrada')
    modes=[{'id':'SPIN','kind':'SPIN','stake':format(stake,'.2f'),'price_multiplier':'1',
            'required_options':['spin'],'server_declared':True}]
    for name in allowed:
        quote=quotes[name];kind={'FREESPIN':'PURCHASE','BOOSTED_BET':'FEATURE_SPIN','BOOSTED_BET_X_ROWS':'FEATURE_SPIN'}.get(quote.get('type'),'UNKNOWN_FEATURE')
        price=_money(quote.get('price'),positive=True)
        domain=levels.get(name)
        if not isinstance(domain,list) or not domain:raise Unlearned('Nolimit City: faltan apuestas permitidas para '+name)
        value=min(_money(v,positive=True) for v in domain)
        if value!=value.quantize(Decimal('.01')):raise Unlearned('Nolimit City: escala de apuesta modificada no demostrada')
        if kind=='PURCHASE' and (config.get('featureBuyEnabled') is not True or 'BONUS_BUY' not in types):
            raise Unlearned('Nolimit City: compra contradice la habilitación del servidor')
        if kind=='FEATURE_SPIN' and (config.get('boostedBetAllowed') is not True or 'BOOSTED_BET' not in types):
            raise Unlearned('Nolimit City: apuesta mejorada contradice la habilitación del servidor')
        if quote.get('type')=='BOOSTED_BET_X_ROWS' and (config.get('boostedBetExtraRows') is not True or 'BOOSTED_BET_X_ROWS' not in types):
            raise Unlearned('Nolimit City: filas mejoradas sin habilitación del servidor')
        if quote.get('additionalTypes') not in (None,[]):kind='UNKNOWN_FEATURE'
        modes.append({'id':('BUY_' if kind=='PURCHASE' else 'BOOST_' if kind=='FEATURE_SPIN' else 'UNKNOWN_')+name,
            'kind':kind,'selector':name,'server_type':quote.get('type'),'price_multiplier':str(price),
            'stake':format(value,'.2f'),'required_options':[name],'server_declared':True})
    if (init.get('currency') or {}).get('code')!='EUR':raise Unlearned('Nolimit City: escala monetaria no demostrada para esta moneda')
    if require_idle:require_idle_initial_state(init)
    complete=all(m['kind']!='UNKNOWN_FEATURE' for m in modes)
    source='init.game.featureBuyTimesBetValue/allowedFeatureBets/featureBetLevels'
    domains={category:{'complete':complete,'source':source,'options':[m.get('selector') for m in modes if m['kind']==kind]}
             for category,kind in [('purchase','PURCHASE'),('feature_spin','FEATURE_SPIN')]}
    # BOOSTED_BET proves its server category, not an antebet UI role.
    for mode in modes:
        mode['declared_feature_options']=list(allowed)
        mode['declared_purchase_options']=[item['selector'] for item in modes if item['kind']=='PURCHASE']
        mode['declared_feature_categories']=[category for category,kind in [('BONUS_BUY','PURCHASE'),('BOOSTED_BET','FEATURE_SPIN')]
            if any(item['kind']==kind for item in modes)]
        if _row_response(game):mode['response_profile']='rows_freespin_and_collect/v1'
        mode['wire_command']='normalBet' if mode['kind']=='SPIN' else 'featureBet'
        mode.update(executable=mode['kind']!='UNKNOWN_FEATURE',validated=False,coverage_required=True,
                    covered_options=[],sample_counts={},evidence_level='SERVER_ADVERTISED',observed=False,
                    request_shape={'type':'normalBet','bet':mode['stake']} if mode['kind']=='SPIN' else
                        {'type':'featureBet','bet':mode['stake'],'featureName':mode['selector'],'playerInteraction':{'featureName':mode['selector']}})
    return modes,domains

def normalized_response(answer, declared_options=(), declared_categories=(),declared_purchase_options=()):
    """Normalize proven server fields without treating catalog entries as choices."""
    answer=dict(answer);game=dict(answer.get('game') or {})
    explicit_no_extra=game.get('wasExtraSpin') is False
    legacy=all(key in game for key in ('thisSpinWinning','totalSpinWinnings','enhancedBet','featureName','firstStage','secondStage','secondStageFsLeft'))
    if legacy:
        if type(game['enhancedBet']) is not bool:raise Unlearned('Nolimit City: indicador enhancedBet inválido')
        if 'wasBoostedBet' in game and game['wasBoostedBet'] is not game['enhancedBet']:
            raise ValueError('Nolimit City: indicadores de apuesta mejorada contradictorios')
        game['wasBoostedBet']=game['enhancedBet']
        if 'wasExtraSpin' not in game:game['wasExtraSpin']=False
        if 'win' in game and _money(game['win'])!=_money(game['thisSpinWinning']):
            raise ValueError('Nolimit City: indicadores de premio contradictorios')
        game['win']=game['thisSpinWinning']
    boosted_dialect=_boosted_response(game)
    category_dialect=_category_response(game)
    if boosted_dialect:
        if type(game['boostedBet']) is not bool:raise Unlearned('Nolimit City: indicador boostedBet inválido')
        if 'wasBoostedBet' in game and game['wasBoostedBet'] is not game['boostedBet']:
            raise ValueError('Nolimit City: indicadores de apuesta mejorada contradictorios')
        game['wasBoostedBet']=game['boostedBet']
    elif category_dialect:
        if 'wasBoostedBet' in game and game['wasBoostedBet'] is not False:
            raise ValueError('Nolimit City: indicadores de apuesta mejorada contradictorios')
        game['wasBoostedBet']=False
    if boosted_dialect or category_dialect:
        # All normal/feature/zeroBet steps of these captured dialects omit this
        # optional acknowledgment. Explicit extra spins remain unsupported.
        if 'wasExtraSpin' not in game:game['wasExtraSpin']=False
        if 'totalSpinWinnings' in game and not _batch_response(game):
            if 'win' in game and _money(game['win'])!=_money(game['totalSpinWinnings']):
                raise ValueError('Nolimit City: indicadores de premio contradictorios')
            game['win']=game['totalSpinWinnings']
        if game.get('nextMode')=='NORMAL' and game.get('respinsLeft',0)!=0:
            raise Unlearned('Nolimit City: respin todavía pendiente')
    batch_dialect=_batch_response(game)
    if batch_dialect:
        flags=[]
        for key in ('boostedBet','boostedBetPlayed','enhancedBet'):
            if key not in game:continue
            value=game[key]
            if type(value) is bool:flags.append(value)
            elif key=='enhancedBet' and type(value) is int and value>=0:flags.append(value>0)
            else:raise Unlearned('Nolimit City: indicador de apuesta mejorada inválido: '+key)
        if len(set(flags))!=1 or ('wasBoostedBet' in game and game['wasBoostedBet'] is not flags[0]):
            raise ValueError('Nolimit City: indicadores de apuesta mejorada contradictorios')
        game['wasBoostedBet']=flags[0]
        if 'wasExtraSpin' not in game:game['wasExtraSpin']=False
        step=game.get('thisSpinWinning',game.get('thisSpinWinnings',game['totalSpinWinnings']))
        if 'win' in game and _money(game['win'])!=_money(step):
            raise ValueError('Nolimit City: indicadores de premio contradictorios')
        game['win']=step
    if _extra_response(game):
        if 'wasExtraSpin' in (answer.get('game') or {}) and answer['game']['wasExtraSpin'] is not game['isExtraSpin']:
            raise ValueError('Nolimit City: indicadores de extra spin contradictorios')
        game['wasExtraSpin']=game['isExtraSpin']
    if _level_response(game):
        if game.get('nextMode')=='NORMAL':
            for key in ('respinsLeft','secondStageFsLeft'):
                if key in game and (type(game[key]) is not int or game[key]!=0):
                    raise Unlearned('Nolimit City: contador pendiente o desconocido: '+key)
        if game.get('wasBoostedBet',False) is not False or game.get('wasExtraSpin',False) is not False:
            raise Unlearned('Nolimit City: modificador incompatible con perfil avalanche')
        game['wasBoostedBet']=False;game['wasExtraSpin']=False
        if 'win' in game and _money(game['win'])!=_money(game['totalSpinWinnings']):
            raise ValueError('Nolimit City: premios contradictorios')
        game['win']=game['totalSpinWinnings']
    if _row_response(game):
        if type(game.get('featureBet')) is not bool or not isinstance(game.get('gambleOptions'),dict):
            raise Unlearned('Nolimit City: perfil de filas incompleto')
        boosted=(game['featureBet'] or game['playedRowsInBase']>3) and not game['wasFeatureBuy']
        if 'wasBoostedBet' in game and game['wasBoostedBet'] is not boosted:
            raise ValueError('Nolimit City: indicadores de filas mejoradas contradictorios')
        if game.get('wasExtraSpin',False) is not False or game.get('extraSpinCost',0)!=0:
            raise Unlearned('Nolimit City: extra spin no aprendido en perfil de filas')
        for key in ('respinsLeft','secondStageFsLeft'):
            if key in game and (type(game[key]) is not int or game[key]!=0):raise Unlearned('Nolimit City: contador desconocido en perfil de filas')
        game['wasBoostedBet']=boosted;game['wasExtraSpin']=False
        if 'win' in game and _money(game['win'])!=_money(game.get('totalSpinWinnings')):
            raise ValueError('Nolimit City: premios contradictorios en perfil de filas')
        game['win']=game['totalSpinWinnings']
        row_features=answer.get('features')
        if isinstance(row_features,dict) and row_features.get('active','') in ('','FREESPIN') and row_features.get('available')==['FREESPIN']:
            answer['features']={**row_features,'available':[]}
            if row_features.get('active')=='FREESPIN':answer['features']['active']=''
    features=answer.get('features')
    if (batch_dialect or category_dialect or _extra_response(game) or _level_response(game)) and isinstance(features,dict):
        active=features.get('active','')
        free_modes={'FREESPIN','SUPER_FREESPIN','FREESPIN_SUPER','FREESPIN_BETTER','FREESPIN_AVALANCHE','SUPER_FREESPIN_AVALANCHE'}
        active_free=(((active in free_modes and (active in declared_options or (declared_purchase_options and active==game.get('nextMode'))))
                or (category_dialect and active=='FREESPINS'))
            and (game.get('nextMode') in free_modes or (game.get('mode') in free_modes
                and game.get('nextMode')=='NORMAL' and game.get('freespinsLeft')==0)))
        active_auto=active in ('STACKED_RESPIN_FS','RESPIN') and _pending_auto_phase(answer,game,explicit_no_extra=explicit_no_extra)
        level_free=(_level_response(game) and active in ('FREESPIN','FREESPIN_SUPER')
            and (game.get('nextMode')==active or (game.get('mode')==active and game.get('nextMode')=='NORMAL')))
        level_root=(_level_response(game) and active in declared_purchase_options and game['wasFeatureBuy'] is True
            and game['mode']=='NORMAL' and game['freespinTriggeredThisSpin'] is True
            and game['numberOfFreespinsPlayed']==0 and game['freespinsLeft']>0
            and game['nextMode'] in ('FREESPIN','FREESPIN_SUPER'))
        level_auto=(_level_response(game) and active==game.get('nextMode') and _pending_auto_phase(answer,game))
        if active not in ('',None) and not (active_free or active_auto or level_free or level_root or level_auto):
            raise Unlearned('Nolimit City: función activa sin primitiva aprendida: '+str(active))
        if 'available' not in features:
            answer['features']={**features,'available':[]}
        else:
            items=features['available']
            if (isinstance(items,list) and items and all(isinstance(item,str) for item in items)
                    and len(items)==len(set(items)) and (set(items)==set(declared_options)
                    or (declared_categories and set(items)==set(declared_categories))
                    or (declared_purchase_options and set(items)==set(declared_purchase_options)))):
                answer['features']={**features,'available':[]}
    available=(answer.get('features') or {}).get('available')
    if (legacy and available and isinstance(available,list) and declared_options
            and all(isinstance(item,str) for item in available)
            and len(available)==len(set(available))
            and set(available)==set(declared_options)):
        # Exact init-advertised purchase/boost catalog, not a stage choice domain.
        answer['features']={**answer.get('features',{}),'available':[]}
    if category_dialect and available==['FREESPINS']:
        answer['features']={**answer.get('features',{}),'available':[]}
    if (answer.get('features') or {}).get('available')!=[]:
        raise Unlearned('Nolimit City: elección sin primitiva aprendida: '+json.dumps(available,ensure_ascii=True))
    if legacy and game.get('nextMode')=='NORMAL' and game['secondStageFsLeft']!=0:
        raise Unlearned('Nolimit City: segunda etapa todavía pendiente')
    answer['game']=game
    return answer

class RoundLedger:
    def __init__(self,before,mode):
        self.before=_money(before);self.mode=mode;self.stake=_money(mode['stake'],positive=True)
        self.cost=(self.stake*_money(mode['price_multiplier'],positive=True)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        if self.cost>self.before:raise Unlearned('Nolimit City: saldo Demo insuficiente para la opción declarada')
        self.win=Decimal(0);self.steps=0;self.after=self.before;self.closed=False;self.had_feature=False;self.previous=None;self.extra_played=False;self.extra_cost=Decimal(0)
    def accept(self,answer,request=None):
        answer=normalized_response(answer,self.mode.get('declared_feature_options',()),self.mode.get('declared_feature_categories',()),self.mode.get('declared_purchase_options',()))
        game=answer.get('game')
        if not isinstance(game,dict):raise Unlearned('Nolimit City: falta estado de juego')
        if self.steps==0:
            if _money(game.get('playedBetValue'))!=self.stake:raise ValueError('Nolimit City: apuesta base no coincide')
            if self.mode['kind']=='PURCHASE':
                if game.get('wasFeatureBuy') is not True:raise ValueError('Nolimit City: compra no confirmada')
            elif self.mode['kind']=='FEATURE_SPIN':
                if game.get('wasFeatureBuy') is not False or game.get('wasBoostedBet') is not True:raise ValueError('Nolimit City: modificador no confirmado')
            elif game.get('wasFeatureBuy') is not False or game.get('wasBoostedBet') is not False:
                raise ValueError('Nolimit City: giro normal con modificador inexplicado')
        delta=None
        previous=self.previous or {}
        if _row_response(previous) and previous.get('nextMode')=='GAMBLE':
            if ((request or {}).get('type')!='gambleBet' or _money((request or {}).get('bet'))!=0
                    or (request or {}).get('playerInteraction')!={'gambleCollected':True}
                    or not _row_response(game) or game.get('mode')!='GAMBLE' or game.get('nextMode')!='NORMAL'
                    or game.get('gambleCollect') is not True or _money(game.get('win'))!=0):
                raise Unlearned('Nolimit City: cobro sin petición y acuse contrastados')
        if _extra_response(previous) and previous.get('nextMode')=='EXTRA_SPIN':
            interaction=(request or {}).get('playerInteraction') or {}
            selected=interaction.get('playExtraSpin')
            if (request or {}).get('type')!='zeroBet' or _money((request or {}).get('bet'))!=0 or set(interaction)!={'playExtraSpin'} or selected not in ('yes','no'):
                raise Unlearned('Nolimit City: decisión extra spin sin petición contrastada')
            price=_money(previous.get('extraSpinCost'),positive=True)
            if not _extra_response(game) or game.get('mode')!='EXTRA_SPIN' or _money(game.get('extraSpinCost'),positive=True)!=price:
                raise Unlearned('Nolimit City: precio o transición extra spin no confirmado')
            if selected=='yes':
                if self.win<price or game.get('isExtraSpin') is not True or game.get('nextMode')!='FREESPIN' or game.get('freespinsLeft')!=1 or Decimal(str(game.get('win')))!=-price:
                    raise ValueError('Nolimit City: descuento del giro extra no coincide con la cotización')
                delta=-price;self.extra_cost+=price;self.extra_played=True
            elif game.get('nextMode')!='NORMAL' or _money(game.get('win'))!=0:
                raise ValueError('Nolimit City: rechazo extra spin sin liquidación')
        if game.get('wasExtraSpin') is not False and not (_extra_response(game) and self.extra_played):
            raise Unlearned('Nolimit City: extra spin sin contrato aprendido')
        self.steps+=1;self.win+=_money(game.get('win')) if delta is None else delta
        self.previous=dict(game)
        if self.win!=_money(game.get('accumulatedRoundWin')):raise ValueError('Nolimit City: premio acumulado incoherente')
        self.closed=_closed(answer);self.had_feature|=game.get('nextMode')!='NORMAL'
        expected=self.before-self.cost+(self.win if self.closed else Decimal(0))
        if answer.get('balance') is not None:
            self.after=_money(answer['balance'])
            if self.after!=expected:raise ValueError('Nolimit City: saldo no explica coste y liquidación')
            balances=answer.get('balances')
            if isinstance(balances,dict) and 'TOTAL_BALANCE' in balances and _money(balances['TOTAL_BALANCE'])!=self.after:
                raise ValueError('Nolimit City: saldos del servidor contradictorios')
        elif self.steps==1 or self.closed:raise ValueError('Nolimit City: falta saldo al apostar o liquidar')
        return self.closed
    def proof(self):return {'schema':MONETARY,'before':str(self.before),'cost':str(self.cost),'win':str(self.win),
                           'after':str(self.after),'steps':self.steps,'closed':self.closed,'had_feature':self.had_feature,'extra_spin_cost':str(self.extra_cost)}

def continuation(answer,*,declared_options=(),declared_categories=(),declared_purchase_options=()):
    explicit_no_extra=(answer.get('game') or {}).get('wasExtraSpin') is False
    answer=normalized_response(answer,declared_options,declared_categories,declared_purchase_options)
    available=(answer.get('features') or {}).get('available')
    if available!=[]:raise Unlearned('Nolimit City: elección sin primitiva aprendida: '+json.dumps(available,ensure_ascii=True))
    game=answer.get('game') or {}
    left=game.get('freespinsLeft')
    second=game.get('secondStageFsLeft')
    stage_transition=(type(left) is int and left==0 and type(second) is int and second>0
        and game.get('firstStage') is True and game.get('secondStage') is False
        and all(key in game for key in ('thisSpinWinning','totalSpinWinnings','enhancedBet','featureName')))
    if _pending_auto_phase(answer,game,explicit_no_extra=explicit_no_extra):return {'type':'zeroBet','bet':'0.00'}
    if (_batch_response(game) and game.get('nextMode') in declared_purchase_options
            and type(left) is int and left>0):return {'type':'zeroBet','bet':'0.00'}
    if (_extra_response(game) and game.get('nextMode') in ('FREESPIN_TRIGGER','COIN_SPIN')
            and game.get('isExtraSpin') is False and type(left) is int and left==0
            and game.get('extraSpinCost',0)==0):return {'type':'zeroBet','bet':'0.00'}
    if (_row_response(game) and game.get('nextMode')=='FREESPIN_PICK' and game['wasFeatureBuy'] is True
            and type(game.get('playerSelection')) is int and game['playerSelection']>0
            and game['featureBuyRows']==game['playedRowsInFS'] and left>0):return {'type':'zeroBet','bet':'0.00'}
    if _boosted_response(game):
        if game.get('nextMode')=='RESPIN' and type(game.get('respinsLeft')) is int and game['respinsLeft']>0:
            return {'type':'zeroBet','bet':'0.00'}
        if game.get('nextMode')=='FREESPIN_MINIGAME' and type(left) is int and left>0:
            return {'type':'zeroBet','bet':'0.00'}
    if (game.get('nextMode') not in {'FREESPIN','FREESPIN_BETTER','FREESPIN_SUPER','SUPER_FREESPIN'}
            or (not stage_transition and (type(left) is not int or left<=0))):
        raise Unlearned('Nolimit City: continuación desconocida: '+str(game.get('nextMode')))
    return {'type':'zeroBet','bet':'0.00'}
