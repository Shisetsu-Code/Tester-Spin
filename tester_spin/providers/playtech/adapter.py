"""Executable GPAS adapter sharing the existing Playtech catalog."""
import json
import re
import time
import uuid
from pathlib import Path
from tester_spin.models import GameTestResult, SpinAttempt, utc_now_iso
from tester_spin.providers.catalogs.adapter import CatalogProvider
from tester_spin.providers.catalogs.sources import SOURCES
from .protocol import resolve_configuration
from .primitives import COMMAND, client_contract, discover_modes, entry_command, PickState, RoundLedger
from .direct_runtime import DemoSession


class PlaytechProvider(CatalogProvider):
    key='playtech'
    display_name='Playtech'
    catalog_url=SOURCES['playtech']['url']
    execution_supported=True
    max_test_concurrency=2
    session_factory=DemoSession

    def test_game(self,game,*,spins,timeout_s,stop_event,progress):
        if not re.fullmatch(r'gpas_[A-Za-z0-9_]+',game.symbol or ''):
            result=super().test_game(game,spins=spins,timeout_s=timeout_s,stop_event=stop_event,progress=progress)
            result.error='Motor Playtech no GPAS: contrato pendiente; se conserva el catálogo y la evidencia.'
            return result
        start=time.monotonic();run=self.har_artifact_dir(game)/'runs'/(time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]);run.mkdir(parents=True)
        result=GameTestResult(self.key,game.slug,game.name,game.url,spins,0,0,'PARCIAL',symbol=game.symbol,run_dir=str(run))
        issues=[];pending={}
        try:
            if stop_event.is_set():raise InterruptedError('DETENIDO')
            with self.session_factory(game.symbol,run,timeout_s,stop_event) as session:
                contract=client_contract(session.manifest,session.sources)
                resolved=resolve_configuration(session.config,{'betType':'default'})
                plan=discover_modes(resolved,contract,session.sources)
                result.discovered_modes=plan['modes'];result.feature_domains=plan['domains'];issues.extend(plan['unresolved'])
                result.structural_map['playtech_protocol']={'contract':contract,'source_sha256':session.source_hashes,'configuration':resolved,'fresh_demo':True,'transport':getattr(session,'transport_kind','unspecified')}
                (run/'bootstrap.json').write_text(json.dumps({'manifest':session.manifest,'configuration':resolved,'contract':contract,'source_sha256':session.source_hashes},indent=2),encoding='utf-8')
                base=next((m for m in plan['modes'] if m['kind']=='SPIN'),None)
                if base is None:raise ValueError('BASE_MODE_UNBOUND')
                sequence=[m for m in plan['modes'] if m['kind']!='UNKNOWN_FEATURE' for _ in range(max(1,int(spins)))]
                result.requested_spins=len(sequence)+1
                for index,mode in enumerate(sequence+[dict(base,id=base['id'],return_to_base=True)],1):
                    if stop_event.is_set():raise InterruptedError('DETENIDO')
                    directory=run/('mode-'+str(index));directory.mkdir()
                    attempt=SpinAttempt(index,False,mode_id=mode['id'],mode_kind=mode['kind'],symbol=game.symbol,artifact_dir=str(directory))
                    result.attempts.append(attempt);clock=time.monotonic()
                    ledger=RoundLedger(session.balance,mode['id'],mode['cost']*mode['multiplier']);picks=PickState()
                    request=entry_command(mode,contract)
                    (directory/'request.json').write_text(json.dumps(request,indent=2),encoding='utf-8')
                    try:
                        for step in range(200):
                            response=session.exchange(request,contract)
                            (directory/('response.json' if step==0 else f'response-{step}.json')).write_text(json.dumps(response,indent=2),encoding='utf-8')
                            data=ledger.accept(response);attempt.wire_steps+=1
                            if ledger.closed:break
                            parameters=picks.parameters(data,contract['pick_bound'])
                            if not data.get('nextRound'):raise ValueError('CONTINUATION_STATE_UNKNOWN')
                            request={'_type':COMMAND,'gameData':{'_type':contract['class'],'ID':contract['continuation_id'],'parameters':parameters}}
                            if contract['dialect']=='modern':request['autoplay']=False
                            (directory/f'request-{step+1}.json').write_text(json.dumps(request,indent=2),encoding='utf-8')
                        if not ledger.closed:raise ValueError('ROUND_STEP_LIMIT')
                        session.wait(lambda:ledger.verify(session.balance),'BALANCE_NOT_RECONCILED')
                        attempt.ok=True;attempt.terminal=True;result.successful_spins+=1
                        mode['validated']=True
                        for phase,options in picks.offered.items():
                            mode.setdefault('choice_domains',[]).append({'id':phase,'options':sorted(options),'covered':sorted(picks.selected.get(phase,set())),'source':'fresh_response.listPickPlayerPickOptions'})
                        missing=picks.pending()
                        if missing:pending[str(index)]=missing;issues.append('CHOICE_BRANCHES_PENDING:'+mode['name'])
                        if mode.get('return_to_base'):result.structural_map['return_to_base_verified']=True
                        (directory/'summary.json').write_text(json.dumps({'closed':True,'stake':ledger.cost,'win':ledger.wins,'balance_before':ledger.before,'balance_after':session.balance,'pending_choice_branches':missing},indent=2),encoding='utf-8')
                        progress(f"[{game.name}] {mode['name']}: ronda cerrada, coste {ledger.cost}, premio {ledger.wins}.")
                    except Exception as exc:
                        attempt.error=str(exc);issues.append(str(exc));raise
                    finally:attempt.elapsed_ms=(time.monotonic()-clock)*1000
                if session.errors:issues.extend(session.errors)
        except Exception as exc:
            reason=type(exc).__name__+': '+str(exc)
            if reason not in issues:issues.append(reason)
        result.failed_spins=sum(not a.ok for a in result.attempts)
        result.structural_map['pending_choice_branches']=pending
        result.structural_map['execution_issues']=list(dict.fromkeys(issues))
        result.status='OK' if not issues and result.attempts and all(a.ok for a in result.attempts) and result.structural_map.get('return_to_base_verified') else 'PARCIAL'
        result.error='; '.join(dict.fromkeys(issues))
        result.finished_at=utc_now_iso();result.elapsed_ms=(time.monotonic()-start)*1000
        (run/'result.json').write_text(json.dumps(result.to_dict(),indent=2),encoding='utf-8')
        progress(f'[{game.name}] {result.status}: {result.successful_spins} rondas completas. '+result.error)
        return result
