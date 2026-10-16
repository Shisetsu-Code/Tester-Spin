from pathlib import Path
import pytest
from tester_spin.providers.nolimit_city.client_money import monetary_fields
from tester_spin.providers.nolimit_city.operation_fields import step_win,round_win

SOURCE='e.Parser=class{getActionSpinOptions(){return{getParsedData:(data,history,context)=>({totalWin:data.roundPrize,totalSpinWinnings:this.getPrize(data,context)})}}getPrize(record,unused){return record.responsePrize}};'


def test_ordered_subset_binds_actual_arguments_to_getter_formals():
    assert monetary_fields(SOURCE)=={'spin':'responsePrize','round':'roundPrize'}
    assert step_win({'responsePrize':.12},client_source=SOURCE)==.12
    assert round_win({'roundPrize':.34},client_source=SOURCE)==.34


@pytest.mark.parametrize('source',[
    SOURCE.replace('this.getPrize(data,context)','this.getPrize(history,context)'),
    SOURCE.replace('this.getPrize(data,context)','this.getPrize(data,context,history)').replace('getPrize(record,unused)','getPrize(record,unused,last)'),
    SOURCE.replace('return record.responsePrize','return unused.responsePrize'),
    SOURCE.replace('this.getPrize(data,context)','getPrize(data,context)'),
    SOURCE.replace('return record.responsePrize','record.responsePrize=99;return record.responsePrize'),
    SOURCE.replace('getPrize(record,unused)','getPrize(record,record)'),
    SOURCE.replace('this.getPrize(data,context)','this.getPrize(data,data)'),
    SOURCE.replace('getParsedData:(data,history,context)','getParsedData:(data,data,context)'),
    SOURCE.replace('e.Parser=class{','e.Parser=class{constructor(){this.getPrize=unknown}'),
    SOURCE.replace('e.Parser=class{','e.Parser=class{constructor(){this["getPrize"]=unknown}'),
])
def test_subset_proof_rejects_missing_reordered_mutated_or_ambiguous_data(source):
    assert monetary_fields(source) is None


@pytest.mark.skipif(not Path('data/providers/nolimit_city/_clients/Payday/1.1.9.js').is_file(),reason='Exact public client cache not supplied')
def test_exact_public_payday_client_uses_its_direct_response_prize_getter():
    source=Path('data/providers/nolimit_city/_clients/Payday/1.1.9.js').read_text(encoding='utf-8')
    assert monetary_fields(source)=={'spin':'thisResponseWinnings','round':'accumulatedRoundWin'}
