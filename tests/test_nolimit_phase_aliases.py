"""Wire phases can be assigned before exporting their enum class."""
import pytest
from tester_spin.providers.nolimit_city.client_actions import automatic_command


SOURCE='''({1(m,e,r){const a=r(2),p=r(3);g.addGameModeFlowStatePresentationMap(a.Modes.SHORT,new Map([[f.FlowState.IDLE,new p.Auto]]))},2(m,e,r){const b=r(4);class M extends b.GameMode{}M.SHORT="CONTINUE_WIRE",e.Modes=M},3(m,e){e.Auto=class{start(c){g.apiPlugin.betHandler.zeroBet(),c.finish()}}},4(m,e){class B{}e.GameMode=B}})'''
ANSWER={'game':{'mode':'NORMAL','nextMode':'CONTINUE_WIRE'}}


def test_export_after_static_fields_preserves_the_wire_phase_binding():
    assert automatic_command(SOURCE,ANSWER)=={'type':'zeroBet','bet':'0.00'}


@pytest.mark.parametrize('old,new',[
    ('M.SHORT="CONTINUE_WIRE"','M.SHORT="OTHER"'),
    ('M.SHORT="CONTINUE_WIRE"','flag&&(M.SHORT="CONTINUE_WIRE")'),
    ('e.Modes=M','e.Modes=M;M.SHORT="OTHER"'),
    ('e.Modes=M','e.Modes=M;M["SHORT"]="OTHER"'),
    ('e.Modes=M','e.Modes=M;Object.assign(M,other)'),
    ('e.Modes=M','e.Modes=M;Object.defineProperty(M,"SHORT",other)'),
    ('e.Modes=M','e.Modes=M;const alias=M;alias.SHORT="OTHER"'),
    ('const a=r(2),p=r(3);','const a=r(2),p=r(3);a.Modes.SHORT="OTHER";'),
    ('const a=r(2),p=r(3);','const a=r(4),p=r(3);'),
    ('g.apiPlugin.betHandler.zeroBet()','g.apiPlugin.betHandler.zeroBet({unknown:1})'),
])
def test_alias_resolution_does_not_infer_through_mutations_or_another_import(old,new):
    assert automatic_command(SOURCE.replace(old,new),ANSWER) is None


def test_same_minified_reference_from_another_module_cannot_borrow_the_enum():
    source=SOURCE[:-2]+',5(m,e,r){const a=r(4);use(a.Modes.SHORT)}})'
    assert automatic_command(source,ANSWER) is None
