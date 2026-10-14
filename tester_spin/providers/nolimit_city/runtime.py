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
        self.socket=None;self.rows=[];self.capture=None;self.remembered={};self.counter=0;self.uuid=uuid.uuid4().hex
    def open(self,game,http,timeout,stop,directory):
        self.timeout=max(.1,float(timeout));self.stop=stop
        response=http.get(CDN+game.symbol+'/info.json',timeout=self.timeout);response.raise_for_status()
        info=response.json();version=info.get('version')
        if info.get('name')!=game.symbol or not isinstance(version,str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',version):
            raise Unlearned('Nolimit City: identidad o versión de cliente desconocida')
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
    def close(self):
        if self.capture is not None:save(self.capture_path,self.capture)
        if self.socket is not None:
            try:self.socket.close()
            except Exception:pass

def require_idle_initial_state(init):
    game=init.get('game') or {}
    if game.get('nextMode')!='NORMAL' or game.get('freespinsLeft')!=0 or init.get('remainingFreeSpins')!=0 or (init.get('features') or {}).get('available',[])!=[]:
        raise Unlearned('Nolimit City: estado inicial sin primitiva aprendida; opciones declaradas conservadas')


def declaration(init, *, require_idle=True):
    game=init.get('game');config=init.get('gameClientConfiguration');allowed=init.get('allowedFeatureBets')
    levels=init.get('featureBetLevels');types=init.get('allowedFeatureTypes')
    if not isinstance(game,dict) or not isinstance(config,dict) or not isinstance(levels,dict) or not isinstance(types,list):
        raise Unlearned('Nolimit City: declaración incompleta de opciones y apuestas')
    table=game.get('featureBuyTimesBetValue')
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
        quote=quotes[name];kind={'FREESPIN':'PURCHASE','BOOSTED_BET':'FEATURE_SPIN'}.get(quote.get('type'),'UNKNOWN_FEATURE')
        price=_money(quote.get('price'),positive=True)
        domain=levels.get(name)
        if not isinstance(domain,list) or not domain:raise Unlearned('Nolimit City: faltan apuestas permitidas para '+name)
        value=min(_money(v,positive=True) for v in domain)
        if value!=value.quantize(Decimal('.01')):raise Unlearned('Nolimit City: escala de apuesta modificada no demostrada')
        if kind=='PURCHASE' and (config.get('featureBuyEnabled') is not True or 'BONUS_BUY' not in types):
            raise Unlearned('Nolimit City: compra contradice la habilitación del servidor')
        if kind=='FEATURE_SPIN' and (config.get('boostedBetAllowed') is not True or 'BOOSTED_BET' not in types):
            raise Unlearned('Nolimit City: apuesta mejorada contradice la habilitación del servidor')
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
        mode['wire_command']='normalBet' if mode['kind']=='SPIN' else 'featureBet'
        mode.update(executable=mode['kind']!='UNKNOWN_FEATURE',validated=False,coverage_required=True,
                    covered_options=[],sample_counts={},evidence_level='SERVER_ADVERTISED',observed=False,
                    request_shape={'type':'normalBet','bet':mode['stake']} if mode['kind']=='SPIN' else
                        {'type':'featureBet','bet':mode['stake'],'featureName':mode['selector'],'playerInteraction':{'featureName':mode['selector']}})
    return modes,domains

def normalized_response(answer, declared_options=()):
    """Normalize proven server fields without treating catalog entries as choices."""
    answer=dict(answer);game=dict(answer.get('game') or {})
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
    boosted_dialect=(all(key in game for key in ('boostedBet','wasFeatureBuy','playedBetValue',
        'accumulatedRoundWin','mode','nextMode','freespinsLeft','freespinsPlayed'))
        and ('win' in game or 'totalSpinWinnings' in game))
    if boosted_dialect:
        if type(game['boostedBet']) is not bool:raise Unlearned('Nolimit City: indicador boostedBet inválido')
        if 'wasBoostedBet' in game and game['wasBoostedBet'] is not game['boostedBet']:
            raise ValueError('Nolimit City: indicadores de apuesta mejorada contradictorios')
        game['wasBoostedBet']=game['boostedBet']
        # Captures prove the absent extra-spin flag only on ordinary closed spins.
        plain_closed=(game['mode']=='NORMAL' and game['nextMode']=='NORMAL'
            and type(game['freespinsLeft']) is int and game['freespinsLeft']==0
            and game['freespinsPlayed']==0 and game.get('respinsLeft',0)==0
            and game['wasFeatureBuy'] is False and game['boostedBet'] is False)
        if plain_closed:
            if 'wasExtraSpin' not in game:game['wasExtraSpin']=False
            if 'totalSpinWinnings' in game:
                if 'win' in game and _money(game['win'])!=_money(game['totalSpinWinnings']):
                    raise ValueError('Nolimit City: indicadores de premio contradictorios')
                game['win']=game['totalSpinWinnings']
        if game.get('nextMode')=='NORMAL' and game.get('respinsLeft',0)!=0:
            raise Unlearned('Nolimit City: respin todavía pendiente')
    available=(answer.get('features') or {}).get('available')
    if (legacy and available and isinstance(available,list) and declared_options
            and all(isinstance(item,str) for item in available)
            and len(available)==len(set(available))
            and set(available)==set(declared_options)):
        # Exact init-advertised purchase/boost catalog, not a stage choice domain.
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
        self.win=Decimal(0);self.steps=0;self.after=self.before;self.closed=False;self.had_feature=False
    def accept(self,answer):
        answer=normalized_response(answer,self.mode.get('declared_feature_options',()))
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
        if game.get('wasExtraSpin') is not False:raise Unlearned('Nolimit City: extra spin sin contrato aprendido')
        self.steps+=1;self.win+=_money(game.get('win'))
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
                           'after':str(self.after),'steps':self.steps,'closed':self.closed,'had_feature':self.had_feature}

def continuation(answer,*,declared_options=()):
    answer=normalized_response(answer,declared_options)
    available=(answer.get('features') or {}).get('available')
    if available!=[]:raise Unlearned('Nolimit City: elección sin primitiva aprendida: '+json.dumps(available,ensure_ascii=True))
    game=answer.get('game') or {}
    left=game.get('freespinsLeft')
    second=game.get('secondStageFsLeft')
    stage_transition=(type(left) is int and left==0 and type(second) is int and second>0
        and game.get('firstStage') is True and game.get('secondStage') is False
        and all(key in game for key in ('thisSpinWinning','totalSpinWinnings','enhancedBet','featureName')))
    if (game.get('nextMode') not in {'FREESPIN','FREESPIN_BETTER','FREESPIN_SUPER','SUPER_FREESPIN'}
            or (not stage_transition and (type(left) is not int or left<=0))):
        raise Unlearned('Nolimit City: continuación desconocida: '+str(game.get('nextMode')))
    return {'type':'zeroBet','bet':'0.00'}
