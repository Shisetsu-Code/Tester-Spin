import importlib.util,json
import re
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]

def test_public_report_is_allowlisted_and_does_not_publish_network_or_sessions():
 from tester_spin.cli import public_report
 report={'provider':'nolimit_city','attempted':1,'pending':0,'reason':'COMPLETED','results':[{'provider':'nolimit_city','slug':'example','status':'OK'}],
  'ip_counts':{'203.0.113.1':1},'private_config':'PrivateKey=secret','future_private_field':{'extPlayerKey':'secret'}}
 safe=public_report(report)
 assert safe=={'provider':'nolimit_city','attempted':1,'pending':0,'reason':'COMPLETED','results':report['results']}
 assert 'secret' not in json.dumps(safe) and '203.0.113.1' not in json.dumps(safe)

def test_workflow_is_manual_selects_one_provider_and_uploads_only_summary():
 path=ROOT/'.github/workflows/provider-run.yml'
 assert path.is_file()
 text=path.read_text(encoding='utf-8')
 assert 'workflow_dispatch:' in text and 'WG_CONFIGS_JSON' in text
 assert 'cancel-in-progress: false' in text
 assert 'path: public-summary.json' in text
 assert 'path: data' not in text and 'path: **' not in text
 assert 'env:' in text and '--games-per-ip' in text

def _workflow_job(text, name):
 # Bound assertions to one top-level job; this is not a general YAML parser.
 jobs=text.split('\njobs:\n',1)[1]
 match=re.search(rf'^  {re.escape(name)}:\n(.*?)(?=^  \S|\Z)',jobs,re.M|re.S)
 assert match is not None, f'Missing workflow job: {name}'
 return match.group(1)

def test_ci_is_callable_by_builds_and_keeps_normal_ci_events():
 text=(ROOT/'.github/workflows/ci.yml').read_text(encoding='utf-8')
 events=text.split('\non:\n',1)[1].split('\n\n',1)[0]
 assert re.findall(r'^  (\w+):',events,re.M)==['push','pull_request','workflow_call']
 assert '  push:\n    branches: [main]' in events

def test_ci_runs_the_complete_pytest_suite_once():
 text=(ROOT/'.github/workflows/ci.yml').read_text(encoding='utf-8')
 test_job=_workflow_job(text,'test')
 # An exact command protects the whole suite from narrowed paths or filters.
 test_commands=[line for line in text.splitlines()
                if re.search(r'\b(?:pytest|unittest)\b',line) and 'pip install' not in line]
 assert test_commands==['        run: xvfb-run -a python -m pytest tests -q']
 assert test_commands[0] in test_job
 assert not re.search(r'^    (?:if|continue-on-error):',test_job,re.M)
 assert not re.search(r'^        (?:if|continue-on-error):',test_job,re.M)

def test_provider_build_requires_successful_local_verification():
 text=(ROOT/'.github/workflows/build-pragmatic.yml').read_text(encoding='utf-8')
 # A relative workflow call uses the caller's commit, without a floating ref.
 assert _workflow_job(text,'verify').strip()=='uses: ./.github/workflows/ci.yml'
 build=_workflow_job(text,'build')
 assert re.search(r'^    needs: verify$',build,re.M)
 # always() or continue-on-error would let a failed verification produce builds.
 assert not re.search(r'^    (?:if|continue-on-error):',build,re.M)

@pytest.mark.parametrize(('filename','job'),[
 ('ci.yml','test'),('build-pragmatic.yml','build'),
])
def test_verification_and_build_checkout_the_default_event_source(filename,job):
 text=(ROOT/'.github/workflows'/filename).read_text(encoding='utf-8')
 job_text=_workflow_job(text,job)
 assert text.count('uses: actions/checkout@')==1
 # A bare checkout selects the event source in both the caller and called job.
 # Reject ref/repository overrides, even if another checkout still uses defaults.
 assert re.search(r'^      - uses: actions/checkout@v4\n(?=      - |\Z)',job_text,re.M)

def test_provider_build_preserves_independent_manual_and_filtered_push_events():
 text=(ROOT/'.github/workflows/build-pragmatic.yml').read_text(encoding='utf-8')
 events=text.split('\non:\n',1)[1].split('\n\n',1)[0]
 assert re.findall(r'^  (\w+):',events,re.M)==['workflow_dispatch','push']
 branches,paths=events.split('    branches:\n',1)[1].split('    paths:\n',1)
 assert re.findall(r'^      - (.+)$',branches,re.M)==['main','feature/standalone-all-providers']
 assert set(re.findall(r"^      - '(.+)'$",paths,re.M))=={
  'launcher.py','provider_launcher.py','run_standalone.py',
  'tester_spin/app.py','tester_spin/app_current.py','tester_spin/updater.py',
  'tester_spin/providers/**','requirements*.txt',
  '.github/workflows/ci.yml','.github/workflows/build-pragmatic.yml',
 }

def test_installed_entry_point_and_catalog_data_are_packaged():
 import tomllib
 project=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))
 assert project['project']['scripts']['tester-spin']=='tester_spin.cli:main'
 assert project['tool']['setuptools']['package-data']['*']==['*.json','*.js','*.html','*.txt']

def test_profile_materialization_does_not_print_secret_or_allow_path_escape(tmp_path,capsys):
 spec=importlib.util.spec_from_file_location('profile_prep',ROOT/'scripts/prepare-wireguard-profiles.py')
 assert spec and spec.loader
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 profile='[Interface]\nPrivateKey = private-value\nAddress = 10.0.0.2/32\n[Peer]\nPublicKey = public-value\nEndpoint = vpn.example:51820\nAllowedIPs = 0.0.0.0/0, ::/0\n'
 with pytest.raises(ValueError):module.materialize(json.dumps({'../outside':profile}),tmp_path/'unsafe')
 assert not (tmp_path/'outside.conf').exists()
 output=tmp_path/'valid';module.materialize(json.dumps({'profile1':profile}),output)
 assert (output/'profile1.conf').read_text(encoding='utf-8')==profile
 assert 'private-value' not in capsys.readouterr().out
