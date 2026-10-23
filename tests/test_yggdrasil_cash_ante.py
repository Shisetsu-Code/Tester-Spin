from copy import deepcopy
import json
from pathlib import Path
import threading

import pytest

from tester_spin.providers.yggdrasil.cash_collect_source import declaration
from tester_spin.providers.yggdrasil.runtime import DemoRuntime, Unsupported

ROOT = Path(__file__).parent / 'fixtures'
DATA = json.loads((ROOT / 'yggdrasil_cash_ante.json').read_text())
SOURCE = (ROOT / 'yggdrasil_cash_collect_source.js').read_text()


def play(tmp_path, payload=None, context=None, source=SOURCE):
    runtime = DemoRuntime(None, '20002', 1, threading.Event(), gate=None)
    constraints = deepcopy(DATA['context']) if context is None else context
    constraints['cash_collect_definition'] = declaration(source)
    runtime.config = {'ordinary_constraints': constraints}
    runtime.call = lambda *args, **kwargs: deepcopy(DATA['payload']) if payload is None else payload
    return runtime.round(DATA['template'], tmp_path)


def test_current_source_and_quote_validate_a_neutral_ante_as_a_feature(tmp_path):
    result = play(tmp_path)
    assert result['known'] and result['terminal'] and not result['base']
    saved = json.loads((tmp_path / 'step-001-response.json').read_text())
    assert saved['ante_cash_collect_outcomes'][0]['schema'] == 'numeric-cash-neutral-ante/v1'
    assert saved['cash_accounting']['debit'] == '0.30'


@pytest.mark.parametrize('mutation', [
    'unknown', 'missing_family_field', 'pending_free', 'wrong_ante_flag', 'active_purchase',
    'counter', 'counter_type', 'multiplier', 'unreconciled_win', 'collector', 'bad_quote', 'no_quote',
])
def test_command_and_terminal_wager_do_not_authorize_an_unknown_cash_outcome(tmp_path, mutation):
    payload = deepcopy(DATA['payload'])
    context = deepcopy(DATA['context'])
    event = payload['data']['wager']['bets'][0]['eventdata']
    data = event['response']['clientData']
    if mutation == 'unknown': data['unlearnedAward'] = {'remaining': 1}
    if mutation == 'missing_family_field': data.pop('modifiersData')
    if mutation == 'pending_free': event['playerState']['freespinsRemaining'] = 1
    if mutation == 'wrong_ante_flag': event['playerState']['goldenBet'] = False
    if mutation == 'active_purchase': event['playerState']['buyBonus'] = True
    if mutation == 'counter': event['playerState']['freespinsPlayed'] = 1
    if mutation == 'counter_type': event['playerState']['freespinsRemaining'] = False
    if mutation == 'multiplier': data['modifiersData']['activeMultiplier'] = 4
    if mutation == 'unreconciled_win': event['response']['cashWin'] = '0.2'
    if mutation == 'collector': data['modifiersData']['collectFish'] = True
    if mutation == 'bad_quote': context['ante_quotes']['GOLDENBET']['amount'] = '0.4'
    if mutation == 'no_quote': context.pop('ante_quotes')
    with pytest.raises(Unsupported, match='cash'):
        play(tmp_path, payload, context)


def test_cash_command_without_current_renderer_is_not_known(tmp_path):
    with pytest.raises(Unsupported, match='cash'):
        play(tmp_path, source='')


def test_ante_command_follows_complete_current_request_builder():
    assert declaration(SOURCE)['ante_command'] == 'GOLDENBET'
    renamed = SOURCE.replace('GOLDENBET', 'EXTRA_CHANCE').replace('LeanderJellyInterface', 'CurrentInterface')
    assert declaration(renamed)['ante_command'] == 'EXTRA_CHANCE'
    changed = SOURCE.replace('e.cmd="GOLDENBET"', 'e.cmd="GOLDENBET",e.amount*=2')
    assert 'ante_command' not in declaration(changed)
