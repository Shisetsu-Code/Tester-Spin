import copy,json
from pathlib import Path
import pytest
from tester_spin.failure_groups import build_report, write_report, select_group

def row(slug='a',provider='playtech',error='CHOICE_BRANCHES_PENDING:BuyFeature',status='PARCIAL',dialect='modern'):
 return {'provider':provider,'slug':slug,'game_name':slug,'status':status,'error':error,'run_dir':'','structural_map':{'playtech_protocol':{'contract':{'dialect':dialect,'entry_id':40021,'continuation_id':48775}},'execution_issues':[error]},'attempts':[]}

def test_same_contract_and_issue_groups_games_not_prices_or_uuid():
 a=row(error='UNBOUND_STAKE_MODE:123e4567-e89b-12d3-a456-426614174000');b=row('b',error='UNBOUND_STAKE_MODE:999e4567-e89b-12d3-a456-426614174000');r=build_report([a,b]);assert len(r['groups'])==1;assert r['groups'][0]['affected']==2

def test_providers_dialects_and_causes_are_not_conflated():
 r=build_report([row(),row('b',provider='other'),row('c',dialect='legacy'),row('d',error='BALANCE_NOT_RECONCILED')]);assert len(r['groups'])==4

def test_groups_rank_by_distinct_games_and_have_two_representatives():
 rows=[row('c'),row('b'),row('a'),row('d',error='GAME_COMMAND_TIMEOUT')];r=build_report(rows+[rows[0]]);assert r['groups'][0]['affected']==3;assert len(r['groups'][0]['representatives'])==2;assert r['attempted']==4

def test_comparison_counts_only_retested_games_and_keeps_missing_pending():
 before=[row('a',status='OK'),row('b'),row('untested')];after=[row('a'),row('b',status='OK'),row('new',status='OK')];r=build_report(after,baseline=before,expected_count=5);assert r['comparison']['regressions']==[['playtech','a']];assert r['comparison']['fixed']==[['playtech','b']];assert r['comparison']['new']==[['playtech','new']];assert r['pending']==2

def test_no_status_mutation_no_secrets_in_report():
 a=row(error='GAME_COMMAND_TIMEOUT token=abc sessionId=private');snapshot=copy.deepcopy(a);r=build_report([a]);assert a==snapshot;assert 'abc' not in json.dumps(r);assert 'private' not in json.dumps(r)

def test_unknown_and_cancelled_are_explicit_not_fake_success():
 r=build_report([row(error='unrecognized response'),row('cancel',status='CANCELADO',error='DETENIDO')]);assert r['groups'];assert r['cancelled']==1;assert r['pending']==0;assert any(g['cause']=='UNKNOWN' for g in r['groups'])

def test_report_and_selection_are_provider_bound(tmp_path):
 paths=write_report([row(),row('b',provider='other')],tmp_path/'batch');d=json.loads(paths['json'].read_text());group=next(g for g in d['groups'] if g['provider']=='playtech');assert select_group(d,group['id'],'playtech')=={'a'}
 with pytest.raises(ValueError):select_group(d,group['id'],'other')
 assert paths['markdown'].exists()

def test_manual_review_emits_grouped_siblings(tmp_path):
 from tester_spin.manual_review import write_review
 p=write_review([row()],tmp_path);assert p.with_suffix('.groups.json').is_file();assert 'Grupos' in p.read_text(encoding='utf-8')


def test_cli_group_retry_includes_now_ok_members(tmp_path,capsys):
 from tester_spin.storage import Storage
 from tester_spin.models import Game,GameTestResult
 from tester_spin.cli import main
 storage=Storage(tmp_path/'tester-spin.sqlite3');game=Game('netent','a','A','https://netent.com/games/a');storage.upsert_games([game]);storage.record_result(GameTestResult('netent','a','A',game.url,1,1,0,'OK'))
 paths=write_report([row(provider='netent')],tmp_path/'prior');report=json.loads(paths['json'].read_text());gid=report['groups'][0]['id']
 assert main(['run','netent','--data-root',str(tmp_path),'--dry-run','--group-report',str(paths['json']),'--group-id',gid])==0
 output=json.loads(capsys.readouterr().out);assert output['selected_games']==['a'];assert output['network_changed'] is False

def test_cli_group_arguments_are_required_together(tmp_path):
 from tester_spin.cli import main
 with pytest.raises(SystemExit):main(['run','netent','--dry-run','--data-root',str(tmp_path),'--group-id','missing'])
 assert not (tmp_path/'tester-spin.sqlite3').exists()


def test_storage_provider_filter_keeps_other_histories_out(tmp_path):
 from tester_spin.storage import Storage
 from tester_spin.models import GameTestResult
 db=Storage(tmp_path/'tester-spin.sqlite3')
 for provider in ('playtech','netent'):db.record_result(GameTestResult(provider,'a','A','https://example.invalid',1,1,0,'OK'))
 assert len(db.latest_results())==2
 assert [r['provider'] for r in db.latest_results('playtech')]==['playtech']


def test_har_artifact_link_is_retained_without_exposing_contents(tmp_path):
 (tmp_path/'session.har').write_text('{"token":"do-not-read"}')
 value=row();value['run_dir']=str(tmp_path);report=build_report([value]);artifact=report['groups'][0]['representatives'][0]['artifacts'];assert artifact.get('har')==str(tmp_path/'session.har');assert 'do-not-read' not in json.dumps(report)

def test_cli_interruption_still_writes_group_report(tmp_path,monkeypatch,capsys):
 from tester_spin.storage import Storage
 from tester_spin.models import Game,GameTestResult
 from tester_spin.cli import main
 import tester_spin.independent.batches as batches
 db=Storage(tmp_path/'tester-spin.sqlite3');games=[Game('playtech',s,s,'https://www.playtechone.com/'+s,symbol='gpas_'+s) for s in ['a','b']];db.upsert_games(games)
 def interrupted(selected,*,record,**kwargs):
  g=selected[0];record(GameTestResult(g.provider,g.slug,g.name,g.url,1,1,0,'OK'));raise RuntimeError('synthetic interruption')
 monkeypatch.setattr(batches,'run_batches',interrupted)
 assert main(['run','playtech','--data-root',str(tmp_path),'--statuses','ALL'])==2
 paths=list((tmp_path/'independent'/'runs').glob('*/summary.groups.json'));assert len(paths)==1
 report=json.loads(paths[0].read_text());assert report['attempted']==1 and report['pending']==1
