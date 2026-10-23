from pathlib import Path
import re

from tester_spin.providers.yggdrasil.cash_collect_source import declaration

SOURCE=(Path(__file__).parent/'fixtures/yggdrasil_cash_collect_source.js').read_text()


def test_current_renderer_declares_every_special_symbol_role():
    proof=declaration(SOURCE)
    assert {key:proof[key] for key in ('wild','cash','collector','scatter')}=={'wild':0,'cash':9,'collector':10,'scatter':11}


def test_roles_follow_source_values_instead_of_title_or_numeric_aliases():
    source=SOURCE.replace('LeanderNiceCatchWildLegaCommunicationService','DifferentRenderer')
    source=re.sub(r'\b(0|9|10|11)==e&&',lambda match:str({'0':42,'9':43,'10':44,'11':45}[match[1]])+'==e&&',source)
    proof=declaration(source)
    assert [proof[key] for key in ('wild','cash','collector','scatter')]==[42,43,44,45]


def test_missing_conflicting_or_noninclusive_renderer_is_not_a_declaration():
    assert declaration(SOURCE+SOURCE) is None
    assert declaration(SOURCE.replace('i.multipliedAmount=t.payout','i.multipliedAmount=t.payout*2')) is None
    assert declaration(SOURCE.replace('a.wildSymbols.push','a.unknownSymbols.push')) is None


def test_current_official_renderer_can_be_loaded_without_guessing_mode_roles(tmp_path):
    from tester_spin.providers.yggdrasil.sdk_mode_roles import load_source
    class Response:
        status_code=200
        def __init__(self,text,url):self.text,self.url=text,url
    class HTTP:
        def get(self,url,timeout):
            if '/init/' in url:return Response('<script src="game.js"></script>','https://staticdemo.yggdrasilgaming.com/20002/index.html')
            return Response(SOURCE,url)
    page='<div data-iframe-src="https://staticdemo.yggdrasilgaming.com/init/launchClient.html?org=Demo&amp;gameid=20002"></div>'
    assert load_source(HTTP(),page,'20002',{'BASIC':{'coinsPerBet':1}},tmp_path,1)==SOURCE
    assert (tmp_path/'sdk-cash-collector-proof.json').exists()
    assert not (tmp_path/'sdk-mode-role-proof.json').exists()
