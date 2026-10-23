import json
from copy import deepcopy
from pathlib import Path
import pytest
from tester_spin.models import GameTestResult,SpinAttempt
from tester_spin.providers.path_coverage import build_path_coverage_report
SCOPE="server_paid_domain_with_resolved_zero_cost_controls/v1"
PROTO="yggdrasil-current-zero-cost-menu/v1"

def setup_result(root):
    directory=root/'BUY_A_BONUS'/'sample-001';directory.mkdir(parents=True)
    result=GameTestResult(provider='yggdrasil',slug='synthetic',game_name='Synthetic',game_url='https://example.invalid',requested_spins=1,successful_spins=1,failed_spins=0,status='OK',run_dir=str(root))
    result.feature_domains={'purchase':{'complete':True},'ante':{'complete':True}}
    result.discovered_modes=[{'id':'BUY_A_BONUS','kind':'PURCHASE','validated':True,'execution_state':'PROVEN_TERMINAL','evidence_level':'REMOTE_EXECUTION','coverage_scope':SCOPE,'required_options':['BUY_A_BONUS'],'covered_options':['BUY_A_BONUS']}]
    result.attempts=[SpinAttempt(number=1,ok=True,terminal=True,mode_id='BUY_A_BONUS',artifact_dir=str(directory))]
    domain=['NON_GAMBLE_3','GAMBLE_3_1']
    initial={'round_ref':'round-1','bets':[{'step':1}], 'choices':{'available':domain,'selected':None,'protocol':PROTO}}
    selected={'round_ref':'round-1','bets':[{'step':1},{'step':2,'command':'NON_GAMBLE_3'}],'transition_validated':True,'choices':{'available':domain,'selected':'NON_GAMBLE_3','protocol':PROTO}}
    for name,payload in [('step-001-response.json',initial),('step-002-response.json',selected),('step-002-request.json',{'cmd':'NON_GAMBLE_3','amount':'0','step':'2'}),('return-to-base.json',{'status':'CONFIRMED','required':2,'consecutive_base':2})]:
        (directory/name).write_text(json.dumps(payload))
    return result,directory

def test_resolved_zero_cost_menu_does_not_require_every_gamble_alternative(tmp_path):
    result,_=setup_result(tmp_path)
    assert build_path_coverage_report(result)['complete']

@pytest.mark.parametrize('damage',['no_ack','foreign_round','charged','unproven','wrong_domain','no_return','foreign_provider','unknown_protocol'])
def test_unresolved_or_unproven_menu_remains_pending(tmp_path,damage):
    result,directory=setup_result(tmp_path)
    path=directory/'step-002-response.json';reply=json.loads(path.read_text())
    if damage=='no_ack':reply['transition_validated']=False
    elif damage=='foreign_round':reply['round_ref']='round-2'
    elif damage=='charged':(directory/'step-002-request.json').write_text(json.dumps({'cmd':'NON_GAMBLE_3','amount':'1','step':'2'}))
    elif damage=='unproven':result.attempts[0].terminal=False
    elif damage=='wrong_domain':reply['choices']['available']=['OTHER']
    elif damage=='no_return':(directory/'return-to-base.json').unlink()
    elif damage=='foreign_provider':result.provider='synthetic'
    elif damage=='unknown_protocol':reply['choices']['protocol']='unknown'
    path.write_text(json.dumps(reply))
    assert not build_path_coverage_report(result)['complete']


def indexed_result(root):
    from tester_spin.providers.yggdrasil.runtime import DemoRuntime, configuration
    fixtures=Path(__file__).parent/'fixtures'
    source=''.join((fixtures/name).read_text() for name in ['yggdrasil_indexed_purchase_roles.js','yggdrasil_indexed_output_source.js','yggdrasil_indexed_awards_source.js'])
    game=json.loads((fixtures/'yggdrasil_indexed_purchase_roles.json').read_text())
    data=json.loads((fixtures/'yggdrasil_indexed_awards.json').read_text())
    runtime=DemoRuntime(None,'20003',1,None);runtime.config=configuration(game,'20003','EUR',sdk_source=source)
    payloads=iter(deepcopy(data['round']));runtime.call=lambda fn,body:next(payloads)
    directory=root/'BUYIN1/sample-001';observed=runtime.round(runtime.config['templates']['BUYIN1'],directory)
    assert observed['known'] and observed['terminal']
    (root/'current-server-configuration.json').write_text(json.dumps(runtime.config))
    (directory/'return-to-base.json').write_text(json.dumps({'status':'CONFIRMED','required':2,'consecutive_base':2}))
    result=GameTestResult(provider='yggdrasil',slug='synthetic-indexed',game_name='Synthetic indexed',game_url='https://example.invalid',requested_spins=1,successful_spins=1,failed_spins=0,status='OK',run_dir=str(root))
    result.feature_domains={'purchase':{'complete':True},'ante':{'complete':True}}
    result.discovered_modes=[{'id':'BUYIN1','kind':'PURCHASE','validated':True,'execution_state':'PROVEN_TERMINAL','evidence_level':'REMOTE_EXECUTION','coverage_scope':SCOPE,'required_options':['BUYIN1'],'covered_options':['BUYIN1']}]
    result.attempts=[SpinAttempt(number=1,ok=True,terminal=True,mode_id='BUYIN1',artifact_dir=str(directory))]
    return result,directory


def test_current_safe_acceptance_can_echo_base_amount_only_with_proven_zero_debit_and_settlement(tmp_path):
    result,directory=indexed_result(tmp_path)
    request=json.loads((directory/'step-002-request.json').read_text())
    assert request['amount']=='0.1' and request['coin']=='0.1'
    assert build_path_coverage_report(result)['complete']
    choice=json.loads((directory/'step-001-response.json').read_text())['choices']
    assert choice['protocol']=='yggdrasil-current-ledger-zero-cost-award/v1'
    assert 'not_all_branches_tested' in choice['scope']


@pytest.mark.parametrize('damage',['charged','wrong_request_amount','missing_queue_proof','pending_free_spins','wrong_source','missing_configuration','nonterminal_collect','wrong_settlement','no_return'])
def test_echoed_amount_choice_keeps_every_accounting_and_terminal_obligation(tmp_path,damage):
    result,directory=indexed_result(tmp_path)
    reply_path=directory/'step-002-response.json';reply=json.loads(reply_path.read_text())
    if damage=='charged':reply['cash_accounting']['debit']='0.1'
    elif damage=='wrong_request_amount':
        path=directory/'step-002-request.json';request=json.loads(path.read_text());request['amount']='1';path.write_text(json.dumps(request))
    elif damage=='missing_queue_proof':reply.pop('indexed_award_proof')
    elif damage=='pending_free_spins':reply['indexed_award_proof']['free_spins_remaining']=1
    elif damage=='wrong_source':
        path=tmp_path/'current-server-configuration.json';config=json.loads(path.read_text());config['ordinary_constraints']['indexed_award_definition']['source_sha256']='0'*64;path.write_text(json.dumps(config))
    elif damage=='missing_configuration':(tmp_path/'current-server-configuration.json').unlink()
    elif damage in {'nonterminal_collect','wrong_settlement'}:
        path=directory/'step-003-response.json';closed=json.loads(path.read_text())
        if damage=='nonterminal_collect':closed['terminal']=False
        else:closed['cash_accounting']['exact_win']='1.80'
        path.write_text(json.dumps(closed))
    else:(directory/'return-to-base.json').unlink()
    reply_path.write_text(json.dumps(reply))
    assert not build_path_coverage_report(result)['complete']
