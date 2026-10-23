"""A registered controller may read a boolean produced by its active parser."""
import pytest
from tester_spin.providers.nolimit_city.client_actions import automatic_command
from test_nolimit_event_actions import bundle as event_bundle


def bundle():
    source=event_bundle()
    source=source.replace('const a=i(2);class C{constructor(){this.GAME_ROUND_CONFIG=()=>({AUTO:{idle:[new a.Step]}})}',
        'const a=i(2),p=i(13),d=i(14);class C{constructor(){this.ZERO_BETS=[()=>new a.Controller],this.SERVER_PARSER=()=>new p.Parser,this.PARSED_GAME_DATA=(raw,parser)=>new d.Data(raw,parser)}')
    start=source.index('2(t,e,i){')
    end=source.index('3(t,e,i){',start)
    source=source[:start]+'2(t,e,i){const b=i(15);class C extends b.Base{constructor(){super()}calculateIsTriggered(raw){return this._nextMode=raw.nextMode,raw.isRespin}shouldShowZeroBetCounter(){return-1!==this._nextMode.indexOf("RESPIN")}}e.Controller=C},'+source[end:]
    return source[:-2]+',13(t,e,i){const m=i(16);e.Parser=class{getNextRespin(raw){return raw.nextMode==m.Modes.RESPIN}}},14(t,e){e.Data=class{constructor(raw,parser){this._respin=parser.getNextRespin(raw)}get isRespin(){return this._respin}}},15(t,e,i){const b=i(3),v=i(4),z=i(5),s=i(17);e.Base=class{get isTriggered(){return this._isTriggered}constructor(){this.addEventListeners()}addEventListeners(){b.Bus.addEventListener(this,s.ServerEvent.INIT_DATA_PARSED,raw=>this.onGameDataParsed(raw.params[0])),b.Bus.addEventListener(this,s.ServerEvent.GAME_DATA_PARSED,raw=>this.onGameDataParsed(raw.params[0]))}onGameDataParsed(raw){this._isTriggered=this.calculateIsTriggered(raw),this._zeroBetNumberLeft=this.getZeroBetNumberLeft(raw)}getZeroBetNumberLeft(raw){return-1}shouldSubtractZeroBetCounter(){return!1}handleZeroBetCounter(){this.shouldShowZeroBetCounter()?(this.shouldSubtractZeroBetCounter()&&this._zeroBetNumberLeft--,b.Bus.dispatchEvent(new v.Event(z.Balance.ZERO_BET,this._zeroBetNumberLeft))):b.Bus.dispatchEvent(new v.Event(z.Balance.ZERO_BET,-1))}}},16(t,e){class M{}M.RESPIN="GENIE_RESPIN",e.Modes=M},17(t,e){class S{}S.INIT_DATA_PARSED="initDataParsed",S.GAME_DATA_PARSED="gameDataParsed",e.ServerEvent=S}})'


def run(source,**fields):
    game={'mode':'NORMAL','nextMode':'GENIE_RESPIN'};game.update(fields)
    return automatic_command(source,{'game':game},direct_demo_transport=True)


def test_active_parser_predicate_reaches_registered_zero_bet_controller():
    assert run(bundle())=={'type':'zeroBet','bet':'0.00'}


@pytest.mark.parametrize('old,new',[
    ('this.SERVER_PARSER=','this.UNUSED_PARSER='),
    ('this.PARSED_GAME_DATA=','this.UNUSED_DATA='),
    ('this.ZERO_BETS=','this.UNUSED_CONTROLLERS='),
    ('super(c.Config.instance)','super(unknown)'),
    ('new d.Data(raw,parser)','new d.Data(parser,raw)'),
    ('parser.getNextRespin(raw)','other.getNextRespin(raw)'),
    ('get isRespin(){return this._respin}','get isRespin(){return unknown}'),
    ('return raw.nextMode==m.Modes.RESPIN','return raw.nextMode==m.Modes.RESPIN||raw.other'),
    ('return raw.nextMode==m.Modes.RESPIN','return raw.mode==m.Modes.RESPIN'),
    ('this._respin=parser.getNextRespin(raw)','this._respin=parser.getNextRespin(raw),this._respin=unknown'),
    ('this._respin=parser.getNextRespin(raw)','parser.getNextRespin=()=>false,this._respin=parser.getNextRespin(raw)'),
    ('this._respin=parser.getNextRespin(raw)','raw.nextMode="OTHER",this._respin=parser.getNextRespin(raw)'),
    ('this._respin=parser.getNextRespin(raw)','const alias=parser;alias.getNextRespin=()=>false;this._respin=parser.getNextRespin(raw)'),
    ('this._respin=parser.getNextRespin(raw)','const alias=raw;alias["nextMode"]="OTHER";this._respin=parser.getNextRespin(raw)'),
    ('this._respin=parser.getNextRespin(raw)','raw=other,this._respin=parser.getNextRespin(raw)'),
    ('this._respin=parser.getNextRespin(raw)','Object.assign(raw,other),this._respin=parser.getNextRespin(raw)'),
    ('this._respin=parser.getNextRespin(raw)','Object.defineProperty(parser,"getNextRespin",other),this._respin=parser.getNextRespin(raw)'),
    ('this._respin=parser.getNextRespin(raw)','delete raw.nextMode;this._respin=parser.getNextRespin(raw)'),
    ('this._slotApi.betHandler.zeroBet()','this._slotApi.betHandler.zeroBet(e)'),
    ('this.calculateIsTriggered(raw)','this.calculateIsTriggered(other)'),
    ('this._isTriggered=this.calculateIsTriggered(raw)','unknown.flag&&(this._isTriggered=this.calculateIsTriggered(raw))'),
    ('this.ZERO_BETS=[()=>new a.Controller]','this.ZERO_BETS=[()=>new a.Unknown,()=>new a.Controller]'),
    ('C.instance=new C}','C.instance=new C;C.instance.SERVER_PARSER=unknown}'),
    ('M.RESPIN="GENIE_RESPIN"','M.RESPIN="OTHER"'),
])
def test_broken_parser_or_controller_provenance_stays_unresolved(old,new):
    assert old in bundle()
    assert run(bundle().replace(old,new)) is None


def test_parsed_predicate_does_not_supply_unknown_or_paid_state_authority():
    assert run(bundle(),nextMode='OTHER') is None
    assert run(bundle(),extraSpinCost=1) is None
    assert run(bundle(),isExtraSpin=True) is None
    assert automatic_command(bundle(),{'game':{'mode':'NORMAL','nextMode':'GENIE_RESPIN'}}) is None
