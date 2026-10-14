from __future__ import annotations
import json,threading,uuid,time
from pathlib import Path
from curl_cffi import requests
from tester_spin.models import GameTestResult,SpinAttempt,utc_now_iso
from tester_spin.providers.base import ProviderAdapter
from .catalog import CODE,CATALOG_URL,FEED_URL,games_from_rows
from .runtime import NolimitSession,Unlearned,declaration,RoundLedger,continuation,save,MONETARY
from tester_spin.providers.result_farm_contract import ProviderFarmSpec,build_result_farm_contract,validate_result_farm_contract

SPEC=ProviderFarmSpec(provider='nolimit_city',protocol_family='nolimit-city-rc4-lzw',
    bootstrap_strategy='nolimit-fanpage-new-demo',transport='websocket-rc4-lzw',
    terminal_contract={'type':'provider','name':'nolimit-settled-round','nextMode':'NORMAL','freespinsLeft':0,'features.available':{'modern':'empty','legacy_two_stage_enhanced_bet':'empty_or_exact_declared_catalog','source':'init.allowedFeatureBets','legacy_required_fields':['thisSpinWinning','totalSpinWinnings','enhancedBet','featureName','firstStage','secondStage','secondStageFsLeft']}},
    mode_option_keys=('selector','server_type','stake','price_multiplier','request_shape','monetary_contract','declared_feature_options'),
    runtime_outputs=('key','extPlayerKey'),protocol_static={'verification_contract':'nolimit-city/verified-runtime/v1',
        'bootstrap_endpoint':'https://demo.nolimitcity.com/EjsFrontWeb/fs','operator':'FANPAGE_DEMO',
        'websocket_path':'/EjsGameWeb/ws/game','outbound_codec':'RC4_HEX_JSON','inbound_codec':'LZW_JSON',
        'protocol':'@nolimitcity/game-communication@0.4.1','free_spin_continuation':{'type':'zeroBet','bet':'0.00'},
        'request_identity_scope':'one_exchange_not_round','declaration_source':'init.game.featureBuyTimesBetValue'})


class NolimitCityProvider(ProviderAdapter):
    key='nolimit_city'
    display_name='Nolimit City'
    catalog_url=CATALOG_URL
    max_test_concurrency=1

    def __init__(self,data_root:Path):
        self.provider_root=Path(data_root)/'providers'/self.key
        self.provider_root.mkdir(parents=True,exist_ok=True)
        self.http=requests.Session(impersonate='chrome')
        self.set_catalog_authority(False,'Catálogo de demos afiliadas: sin autoridad de eliminación')

    def game_dir(self,game):
        if (game.provider!=self.key or not CODE.fullmatch(game.symbol)
                or game.slug!=game.symbol.casefold()):raise ValueError('Nolimit City: identidad inválida')
        path=self.provider_root/game.slug;path.mkdir(parents=True,exist_ok=True)
        return path

    def catalog_record_invalid_reason(self,game):
        try:
            parsed=games_from_rows([{'studio':'Nolimit City','code':game.symbol,'name':game.name,'url':game.url}])[0]
            if game.provider!=self.key or game.slug!=parsed.slug:return 'Nolimit City: identidad inconsistente'
        except ValueError:return 'Nolimit City: fila de catálogo inválida'
        return ''

    def crawl_catalog(self,*,stop_event:threading.Event,progress,max_pages=100,on_game=None):
        self.set_catalog_authority(False,'Feed oficial de demos sin autoridad para borrar juegos')
        if stop_event.is_set():return []
        snapshot=json.loads(Path(__file__).with_name('catalog.json').read_text(encoding='utf-8'))
        games=games_from_rows(snapshot['games'])
        source='snapshot oficial incluido'
        try:
            response=self.http.get(FEED_URL,timeout=30);response.raise_for_status()
            rows=response.json();live=games_from_rows(rows)
            merged={g.symbol:g for g in games};merged.update({g.symbol:g for g in live})
            games=list(merged.values());source=FEED_URL
            (self.provider_root/'catalog.raw.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
        except Exception as exc:
            progress(f'Nolimit City: usando catálogo oficial guardado ({type(exc).__name__}).')
        found=[]
        for game in sorted(games,key=lambda g:g.name.casefold()):
            if stop_event.is_set():break
            folder=self.game_dir(game)
            metadata={'provider':self.key,'slug':game.slug,'symbol':game.symbol,'name':game.name,
                      'public_url':game.url,'demo_url':game.url,'catalog_source':source,'catalog_updated_at':utc_now_iso()}
            (folder/'game.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
            found.append(game)
            if on_game:on_game(game)
        progress(f'Nolimit City: {len(found)} demos cargadas.')
        return found

    def har_artifact_dir(self,game):
        path=self.game_dir(game)/'analysis';path.mkdir(exist_ok=True);return path

    def farm_contract_dir(self,game):return self.game_dir(game)

    def test_game(self,game,*,spins,timeout_s,stop_event,progress):
        requested=max(1,int(spins))
        result=GameTestResult(self.key,game.slug,game.name,game.url,requested,0,requested,'PARCIAL',symbol=game.symbol)
        if stop_event.is_set():
            result.status='CANCELADO';result.error='Ejecución detenida';return result
        start=time.monotonic()
        folder=self.game_dir(game)/'tests'/(utc_now_iso().replace(':','').replace('+','_')+'-'+uuid.uuid4().hex[:8])
        folder.mkdir(parents=True);result.run_dir=str(folder)
        bootstrap=folder/'bootstrap';bootstrap.mkdir()
        session=NolimitSession()
        try:
            init=session.open(game,self.http,timeout_s,stop_event,bootstrap)
            result.discovered_modes,result.feature_domains=declaration(init)
            before=init.get('balance')
            base=result.discovered_modes[0]
            jobs=[base]*requested+[m for m in result.discovered_modes[1:] if m['executable'] for _ in range(requested)]
            def run_round(mode,return_probe=False):
                nonlocal before
                if stop_event.is_set():raise Unlearned('Nolimit City: ejecución detenida')
                directory=folder/f'attempt-{len(result.attempts)+1:03d}';directory.mkdir()
                attempt=SpinAttempt(number=len(result.attempts)+1,ok=False,mode_id='RETURN_SPIN' if return_probe else mode['id'],
                    mode_kind=mode['kind'],symbol=game.symbol,endpoint='wss://demo.nolimitcity.com/EjsGameWeb/ws/game',artifact_dir=str(directory))
                result.attempts.append(attempt)
                ledger=RoundLedger(before,mode)
                content=mode['request_shape'].copy()
                try:
                    for step in range(1,501):
                        if stop_event.is_set():raise Unlearned('Nolimit City: ejecución detenida')
                        save(directory/f'{step:03d}.request.json',{'content':content})
                        answer=session.exchange(content,directory)
                        from .runtime import sanitized
                        save(directory/f'{step:03d}.response.json',sanitized(answer))
                        attempt.wire_steps=step
                        done=ledger.accept(answer)
                        save(directory/'ledger.json',ledger.proof())
                        if done:break
                        content=continuation(answer,declared_options=mode['declared_feature_options'])
                    else:raise Unlearned('Nolimit City: ronda excede el límite de continuaciones')
                    before=ledger.after
                    attempt.ok=attempt.terminal=True;attempt.status_code=200
                    if not return_probe:
                        option='spin' if mode['kind']=='SPIN' else mode['selector']
                        mode.update(validated=True,observed=True,evidence_level='REMOTE_EXECUTION',execution_state='PROVEN_TERMINAL',monetary_contract=MONETARY)
                        mode['covered_options']=[option];mode['sample_counts'][option]=mode['sample_counts'].get(option,0)+1
                        if mode['kind']=='SPIN':result.successful_spins=min(requested,result.successful_spins+1)
                    return not ledger.had_feature
                except Exception as exc:
                    attempt.error=str(exc) if isinstance(exc,(ValueError,TimeoutError)) else type(exc).__name__
                    raise
            for mode in jobs:
                run_round(mode)
                progress(f"Nolimit City {game.name}: {mode['id']} OK.")
            if all(m['validated'] for m in result.discovered_modes):
                consecutive=0
                for _ in range(8):
                    consecutive=consecutive+1 if run_round(base,True) else 0
                    if consecutive>=2:break
                result.structural_map['nolimit_return']={'schema':'nolimit-city/verified-runtime/v1',
                    'status':'CONFIRMED' if consecutive>=2 else 'PENDING','consecutive_base':consecutive}
                if consecutive>=2:result.status='OK'
                else:result.error='Nolimit City: retorno al giro normal no demostrado'
            else:result.error='Nolimit City: categorías declaradas todavía sin primitiva aprendida'
        except Unlearned as exc:
            result.status='CANCELADO' if stop_event.is_set() else 'PARCIAL';result.error=str(exc)
        except Exception as exc:
            result.status='PARCIAL' if result.successful_spins else 'ERROR'
            result.error=str(exc) if isinstance(exc,(ValueError,TimeoutError)) else 'Nolimit City: '+type(exc).__name__+' en la conexión Demo'
            http_status=getattr(getattr(exc,'response',None),'status_code',None)
            if isinstance(http_status,int):result.error=f'Nolimit City: HTTP {http_status} en la conexión Demo'
        finally:
            session.close()
            result.failed_spins=max(0,requested-result.successful_spins)
            result.finished_at=utc_now_iso();result.elapsed_ms=(time.monotonic()-start)*1000
            save(folder/'result.json',result.to_dict())
            metadata_path=self.game_dir(game)/'game.json'
            try:metadata=json.loads(metadata_path.read_text(encoding='utf-8'))
            except (OSError,ValueError):metadata={}
            metadata.update(provider=self.key,symbol=game.symbol,slug=game.slug,name=game.name,public_url=game.url,
                discovered_modes=result.discovered_modes,feature_domains=result.feature_domains)
            save(metadata_path,metadata)
        if result.error:progress(result.error)
        return result

    def build_farm_contract(self,game,result):
        contract=build_result_farm_contract(game,result,self.game_dir(game),SPEC)
        proof=result.structural_map.get('nolimit_return',{})
        roots=[m for m in result.discovered_modes if m.get('kind') in {'SPIN','PURCHASE','FEATURE_SPIN'}]
        if (proof.get('schema')!='nolimit-city/verified-runtime/v1' or proof.get('status')!='CONFIRMED'
                or proof.get('consecutive_base',0)<2 or not roots or any(m.get('monetary_contract')!=MONETARY for m in roots)):
            contract['ready']=False;contract['unresolved'].append('NOLIMIT_CURRENT_MONEY_AND_RETURN_REQUIRED')
        return contract

    def validate_farm_contract(self,contract):
        errors=validate_result_farm_contract(contract,SPEC)
        static=(contract.get('protocol') or {}).get('static') or {}
        if static.get('verification_contract')!='nolimit-city/verified-runtime/v1':errors.append('NOLIMIT_CURRENT_VERIFICATION_REQUIRED')
        if any((m.get('options') or {}).get('monetary_contract')!=MONETARY for m in contract.get('modes',[]) if m.get('kind') in {'SPIN','PURCHASE','FEATURE_SPIN'}):
            errors.append('NOLIMIT_CURRENT_MONEY_REQUIRED')
        return list(dict.fromkeys(errors))
