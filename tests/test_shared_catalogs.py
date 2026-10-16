import json,threading
from pathlib import Path
import pytest

KEYS={'netent','amusnet','playngo','playtech','games_global','greentube','pgsoft','blueprint','relax','playson','wazdan','elk','pushgaming'}

def test_shared_registry_has_all_requested_catalogs(tmp_path):
 from tester_spin.providers.registry import PROVIDERS,create_provider
 assert KEYS <= PROVIDERS.keys()
 for key in KEYS:
  provider=create_provider(key,tmp_path)
  assert provider.key==key
  assert provider.execution_supported is (key=='playtech')

def test_catalog_only_never_invents_buy_counts_or_ok(tmp_path):
 from tester_spin.providers.registry import create_provider
 from tester_spin.models import Game
 provider=create_provider('netent',tmp_path)
 game=Game('netent','test','Test','https://netent.com/games/test')
 result=provider.test_game(game,spins=1,timeout_s=5,stop_event=threading.Event(),progress=lambda _:None)
 assert result.status=='PARCIAL' and not result.attempts
 assert not result.discovered_modes
 assert result.feature_domains['purchase']['declaration_state']=='UNKNOWN'

def test_catalog_snapshot_survives_empty_live_response(tmp_path,monkeypatch):
 from tester_spin.providers.registry import create_provider
 provider=create_provider('relax',tmp_path)
 monkeypatch.setattr(provider,'fetch_live_rows',lambda stop_event,max_pages:[])
 games=provider.crawl_catalog(stop_event=threading.Event(),progress=lambda _:None)
 assert len(games)>20
 assert provider.catalog_crawl_authoritative is False
 assert all(g.provider=='relax' for g in games)

def test_catalog_rejects_foreign_domain_and_duplicate_identity():
 from tester_spin.providers.catalogs.adapter import validate_rows
 good={'slug':'one','name':'One','url':'https://netent.com/games/one'}
 assert len(validate_rows('netent',[good]))==1
 for rows in ([{**good,'url':'https://attacker.invalid/games/one'}],[good,{**good,'name':'Different'}]):
  with pytest.raises(ValueError):validate_rows('netent',rows)

def test_all_entry_points_use_registry_and_bundle_all_catalogs():
 root=Path(__file__).resolve().parents[1]
 text=(root/'tester_spin/app.py').read_text(encoding='utf-8')
 assert 'create_provider' in text and 'for key in PROVIDERS' in text
 assert 'self.registry.register(provider)' not in (root/'tester_spin/app_har.py').read_text(encoding='utf-8')
 assert '--collect-data tester_spin.providers' in (root/'scripts/build-desktop.ps1').read_text(encoding='utf-8')

def test_shared_runtime_cli_uses_updated_app_path(tmp_path,monkeypatch):
 from tester_spin.runtime_entry import cli_command
 python=tmp_path/'pythonw.exe';app=tmp_path/'new-version'
 command,env=cli_command(python,app,{'PYTHONPATH':'stale'},['providers'])
 assert command[0]==str(tmp_path/'python.exe')
 assert command[1:]==['-m','tester_spin.cli','providers']
 assert env['PYTHONPATH'].split(__import__('os').pathsep)[0]==str(app)

def test_unsupported_run_does_not_activate_network_or_execute(tmp_path,monkeypatch,capsys):
 from tester_spin import cli
 monkeypatch.setattr(cli,'profiles_for',lambda args:[])
 assert cli.main(['run','netent','--data-root',str(tmp_path)])==2
 assert 'Ejecutor pendiente' in capsys.readouterr().err
 assert not (tmp_path/'independent').exists()

def test_snapshots_cover_all_registered_catalogs():
 from tester_spin.providers.catalogs.sources import SOURCES
 from tester_spin.providers.catalogs.adapter import validate_rows
 root=Path(__file__).resolve().parents[1]/'tester_spin/providers/catalogs/snapshots'
 for key in SOURCES:
  snapshot=json.loads((root/(key+'.json')).read_text(encoding='utf-8'))
  assert snapshot['provider']==key and snapshot['execution_supported'] is False
  assert len(validate_rows(key,snapshot['games']))>10
  assert 'Bearer' not in json.dumps(snapshot)

def test_legacy_updater_config_migrates_without_losing_data():
 from tester_spin.updater import UpdaterConfig
 old=UpdaterConfig.from_dict({'repo_url':'https://github.com/Shisetsu-Code/Spin-Wire.git','branch':'feat/farm-contract-export-v1','data_dir':'shared/data'})
 assert old.repo_url=='https://github.com/Shisetsu-Code/Tester-Spin.git'
 assert old.branch=='main' and old.data_dir=='shared/data'
 custom=UpdaterConfig.from_dict({'repo_url':'https://example.test/custom.git','branch':'custom'})
 assert custom.repo_url=='https://example.test/custom.git' and custom.branch=='custom'

def test_updated_runtime_is_immutable_for_running_modules(tmp_path):
 import subprocess
 from tester_spin.updater import Updater
 repo=tmp_path/'repo';repo.mkdir();(repo/'run.py').write_text('VERSION=1')
 for args in (['init'],['add','run.py'],['-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','fixture']):
  subprocess.run(['git','-C',str(repo),*args],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 updater=Updater(home=tmp_path/'home')
 pinned=updater.pin_git_runtime(repo,lambda _:None)
 assert pinned!=repo and (pinned/'run.py').read_text()=='VERSION=1'
 (repo/'run.py').write_text('VERSION=2')
 assert (pinned/'run.py').read_text()=='VERSION=1'
 assert updater.pin_git_runtime(repo,lambda _:None)==pinned

def test_public_catalog_parser_does_not_use_menu_labels_as_game_names():
 from tester_spin.providers.catalogs.fetch import parse_html
 rows=parse_html('playson','<a href="/game/one">Play demo</a><a href="/game/one" aria-label="One">One</a>')
 assert len(rows)==1 and rows[0]['name']=='One'

def test_blueprint_symbol_from_slug_is_not_a_buy_or_spin_claim():
 from tester_spin.providers.catalogs.fetch import parse_html
 rows=parse_html('blueprint','<a href="/games/Midas%20King%20of%20Gold"><img alt="Midas King of Gold" src="/logo.png"></a>')
 assert rows[0]['slug']=='Midas%20King%20of%20Gold'
 assert 'purchase' not in rows[0]

def test_cli_uses_the_gui_shared_data_default(monkeypatch,tmp_path):
 from tester_spin.cli import parser
 shared=tmp_path/'shared'/'data'
 monkeypatch.setenv('TESTER_SPIN_DATA_ROOT',str(shared))
 assert parser().parse_args(['catalog','netent']).data_root==shared
 explicit=tmp_path/'explicit'
 assert parser().parse_args(['catalog','netent','--data-root',str(explicit)]).data_root==explicit

def test_updater_can_change_branch_from_old_single_branch_install(tmp_path):
 import subprocess
 from tester_spin.updater import Updater
 origin=tmp_path/'origin';origin.mkdir()
 def git(directory,*args):
  return subprocess.run(['git','-C',str(directory),*args],check=True,capture_output=True,text=True).stdout
 git(origin,'init','-b','main')
 (origin/'run.py').write_text('VERSION=1')
 git(origin,'add','run.py');git(origin,'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','initial')
 git(origin,'checkout','-b','feature')
 (origin/'run.py').write_text('VERSION=2')
 git(origin,'add','run.py');git(origin,'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','feature')
 git(origin,'checkout','main')
 updater=Updater(home=tmp_path/'home');updater.runtime_root.mkdir()
 subprocess.run(['git','clone','--single-branch','--branch','main',str(origin),str(updater.runtime_root/'repo')],check=True,capture_output=True)
 updater.config.repo_url=str(origin);updater.config.branch='feature'
 installed=updater.prepare_runtime(lambda _:None)
 assert (installed/'run.py').read_text()=='VERSION=2'
