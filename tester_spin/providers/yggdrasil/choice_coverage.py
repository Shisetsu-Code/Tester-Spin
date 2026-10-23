"""Proof of a resolved current menu, without asserting every gamble path ran."""
import json
from decimal import Decimal,InvalidOperation,ROUND_HALF_EVEN
from pathlib import Path
from .supermeter import num
SCOPE="server_paid_domain_with_resolved_zero_cost_controls/v1"
PROTOCOL="yggdrasil-current-zero-cost-menu/v1"
LEDGER_PROTOCOL="yggdrasil-current-ledger-zero-cost-award/v1"

def _load(path):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except (OSError,ValueError):return None


def _ledger_choice(result,path,initial,reply,request,step):
    """An echoed base amount is zero cost only with its complete cash proof."""
    config=_load(Path(result.run_dir)/'current-server-configuration.json')
    constraints=config['ordinary_constraints'];rules=constraints['indexed_award_definition'];output=constraints['indexed_output_definition']
    if rules.get('schema')!='indexed-output/current-safe-award-queue/v1' or rules['source_sha256']!=output['source_sha256']:return False
    command=initial['bets'][0]['command'];quote=constraints['purchase_quotes'][command]
    menu={'schema':rules['schema'],'accept':rules['accept'],'risk':rules['risk'],'source_sha256':rules['source_sha256'],'currency':constraints['currency'],'base_amount':constraints['basic_amount'],'paid_command':command}
    if initial.get('indexed_award_menu')!=menu or reply.get('indexed_award_menu')!=menu or initial['choices']['available']!=[rules['accept'],rules['risk']] or reply['choices']['selected']!=rules['accept']:return False
    if set(request)!={'cmd','type','amount','coin','step'} or request['cmd']!=rules['accept'] or request['type']!='bonus' or request['amount']!=constraints['basic_amount'] or request['coin']!=constraints['basic_amount'] or num(request['amount'])<=0:return False
    paid=initial['cash_accounting'];ledger=reply['cash_accounting'];award=reply['indexed_award_proof']
    if paid.get('schema')!='current-cash-ledger/v1' or paid.get('balance_delta_verified') is not True or num(paid['debit'])!=num(quote['amount']) or num(paid['credit'])!=0:return False
    if ledger.get('schema')!='current-cash-ledger/v1' or ledger.get('balance_delta_verified') is not True or num(ledger['debit'])!=0 or num(ledger['credit'])!=0:return False
    if award.get('schema')!='indexed-output/exhausted-award-queues/v1' or award.get('paid_command')!=command:return False
    counts=[award[key] for key in ('initial_free_spins','extra_spins','played_free_spins','nested_respins','free_spins_remaining','respin_lives_remaining')]
    if any(type(value) is not int or value<0 for value in counts) or not counts[0] or counts[2]!=counts[0]+counts[1] or counts[4:]!=[0,0]:return False
    exact=num(award['exact_win']);places=output['currency_decimal_places']
    if exact<0 or type(places) is not int or not 0<=places<=8:return False
    unit=Decimal(1).scaleb(-places)
    if num(ledger['settlement_precision'])!=unit:return False
    settled=exact.quantize(unit,rounding=ROUND_HALF_EVEN)
    for final_path in path.parent.glob('step-*-response.json'):
        final=_load(final_path)
        if not isinstance(final,dict) or final.get('round_ref')!=initial.get('round_ref') or final.get('terminal') is not True or final.get('status')!='Finished' or final.get('next_commands')!=[] or final.get('transition_validated') is not True:continue
        cash=final.get('cash_accounting')
        if not isinstance(cash,dict) or cash.get('schema')!='current-cash-ledger/v1' or cash.get('balance_delta_verified') is not True:continue
        if num(cash['debit'])!=0 or num(cash['exact_win'])!=exact or num(cash['credit'])!=settled or num(cash['settled_win'])!=settled or num(cash['settlement_precision'])!=unit:continue
        final_request=_load(final_path.with_name(final_path.name.replace('-response','-request')))
        if not isinstance(final_request,dict) or final_request.get('cmd')!='C' or num(final_request.get('amount'))!=0 or int(final_request['step'])!=step+1:continue
        if any(bet.get('step')==step+1 and bet.get('command')=='C' for bet in final['bets']):return True
    return False

def resolved_menu(result,mode_id,path,payload,validated):
    if result.provider!='yggdrasil' or not isinstance(payload,dict):return False
    choice=payload.get('choices')
    if not isinstance(choice,dict) or choice.get('protocol') not in {PROTOCOL,LEDGER_PROTOCOL} or choice.get('selected') is not None:return False
    domain=choice.get('available')
    if not isinstance(domain,list) or len(domain)<2 or not all(isinstance(v,str) and v for v in domain) or len(set(domain))!=len(domain):return False
    if not all(result.feature_domains.get(k,{}).get('complete') is True for k in ('purchase','ante')):return False
    if not any(isinstance(m,dict) and m.get('id')==mode_id and m.get('validated') is True and m.get('coverage_scope')==SCOPE and m.get('execution_state')=='PROVEN_TERMINAL' and m.get('evidence_level')=='REMOTE_EXECUTION' for m in result.discovered_modes):return False
    ancestor=next((p for p in path.parents if p.resolve() in validated),None)
    if ancestor is None:return False
    proof=_load(ancestor/'return-to-base.json')
    if not isinstance(proof,dict) or proof.get('status')!='CONFIRMED' or proof.get('required')!=2 or proof.get('consecutive_base',0)<2:return False
    try:prior=max(b['step'] for b in payload['bets'])
    except (KeyError,TypeError,ValueError):return False
    for reply_path in path.parent.glob('step-*-response.json'):
        reply=_load(reply_path)
        if not isinstance(reply,dict) or reply.get('round_ref')!=payload.get('round_ref') or not payload.get('round_ref') or reply.get('transition_validated') is not True:continue
        selected=reply.get('choices',{})
        if not isinstance(selected,dict) or selected.get('protocol')!=choice['protocol'] or selected.get('available')!=domain or selected.get('selected') not in domain:continue
        request=_load(reply_path.with_name(reply_path.name.replace('-response','-request')))
        try:
            step=int(request['step'])
            if request['cmd']!=selected['selected'] or step!=prior+1:continue
            if choice['protocol']==PROTOCOL and Decimal(str(request['amount']))!=0:continue
            if choice['protocol']==LEDGER_PROTOCOL and not _ledger_choice(result,path,payload,reply,request,step):continue
            if not any(b.get('step')==step and b.get('command')==request['cmd'] for b in reply['bets']):continue
        except (KeyError,TypeError,ValueError,InvalidOperation,AttributeError,ArithmeticError):continue
        return True
    return False
