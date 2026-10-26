"""The live orchestration must use the same family serializer as the audit."""
from pathlib import Path
import threading

from tester_spin.models import Game
from tester_spin.providers.playtech.adapter import PlaytechProvider


def test_adapter_preserves_null_parameter_family_through_round_and_return(tmp_path, monkeypatch):
    contract = {'class': 'quickspin.game.playMoney', 'dialect': 'modern',
                'entry_id': 40021, 'continuation_id': 48775, 'pick_bound': False,
                'command_family': 'quickspin-modern', 'command_binding_validated': True}
    # Source binding has separate constructor/registration regressions. This
    # test starts after that pure stage and exercises the real adapter, builders,
    # planner, ledger, operation inventory and return-to-base verification.
    monkeypatch.setattr('tester_spin.providers.playtech.adapter.client_contract',
                        lambda *args, **kwargs: dict(contract))
    commands = []

    class Demo:
        def __init__(self, code, directory, timeout, stop):
            self.directory = Path(directory)
            self.manifest = {'setup': {'useExtendedBetApi': True}}
            self.sources = []
            self.source_hashes = ['stable-family-fixture']
            self.config = [{'scope': {}, 'content': {'game': {
                'costConfiguration': [{'uuid': 'base-cost', 'name': 'default', 'cost': 10}],
                'baseCostMultipliers': [1], 'activeBetOptions': ['default'],
            }}}]
            self.balance = 1000
            self.pending = False
            self.errors = []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def wait(self, predicate, reason):
            if not predicate():
                raise ValueError(reason)

        def exchange(self, command, current_contract):
            commands.append(command)
            game = command['gameData']
            assert game['_type'] == 'quickspin.game.playMoney'
            assert game.get('parameters', 'omitted') is None
            if game['ID'] == 40021:
                assert not self.pending
                assert command['betCost'] == 10
                self.pending = True
                self.balance -= 10
                return {'stakeAmount': 10, 'betCost': 10, 'winAmount': 0,
                        'gameRoundClosed': False, 'gameData': {
                            'stakeCostUuid': 'base-cost', 'stake': 10,
                            'nextRound': 'FreeSpin', 'playIndex': 1, 'totalWinAmount': 0,
                            'playStack': [{'round': 'FreeSpin', 'modeType': 'NORMAL',
                                           'remainingPlayCount': 1}],
                        }}
            assert game['ID'] == 48775 and self.pending
            assert 'betCost' not in command
            self.pending = False
            self.balance += 5
            return {'stakeAmount': 0, 'betCost': 0, 'winAmount': 5,
                    'gameRoundClosed': True, 'gameData': {
                        'stakeCostUuid': 'base-cost', 'stake': 10,
                        'nextRound': 'BET_END_STATE_IDENTIFIER', 'playIndex': 2,
                        'totalWinAmount': 5, 'playStack': [],
                    }}

    provider = PlaytechProvider(tmp_path)
    provider.session_factory = Demo
    game = Game('playtech', 'family-fixture', 'Family Fixture',
                'https://www.playtechone.com/', symbol='gpas_unseen_family_fixture')
    result = provider.test_game(game, spins=1, timeout_s=5,
                                stop_event=threading.Event(), progress=lambda _: None)
    assert result.status == 'OK', result.error
    assert [command['gameData']['ID'] for command in commands] == [40021, 48775, 40021, 48775]
    assert result.successful_spins == 2
    assert result.structural_map['return_to_base_verified'] is True
    assert result.structural_map['operation_inventory']['all_declared_operations_verified'] is True
