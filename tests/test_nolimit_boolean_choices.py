import copy
import pytest
from tester_spin.providers.nolimit_city.choices import choice_domain,confirm_choice
WIRE='pickAndClickBet(e,t=!0){const i={selectedIndex:e.toString()},n={type:s.APIBetType.ZERO_BET,bet:"0.00",playerInteraction:i};this.sendRequest(n,!t)}'
CONFIG='automaticPickGame:{header:()=>"select",optionSelection:e=>{let t=[];for(let i=0;i<e.remainingFlags.length;i++)0==e.remainingFlags[i]&&t.push(i);return t=d.MathHelper.shuffleArray(t),t[0]},type:s.ASBonusPickOptions.PICK_MODE,pickNeededForModes:[c.NeutralMode.PICK],pickNeededForBuyFeatures:[]}'
ENUM='class s extends n.GameMode{}t.NeutralMode=s,s.PICK="UNSEEN_CELLS";'
SOURCE=WIRE+CONFIG+ENUM
ANSWER={'game':{'nextMode':'UNSEEN_CELLS','remainingFlags':[False,True,False]}}

def test_client_loops_full_server_flag_array_and_filters_only_unpicked_cells():
    domain=choice_domain(SOURCE,ANSWER)
    assert domain['options']==[0,1,2] and domain['available']==[0,2]
    assert len(domain['source_sha256'])==64
    confirm_choice(domain,0,{'game':{'remainingFlags':[True,True,False]}})

@pytest.mark.parametrize('flags',[[False,True,False],[True,False,False],[True,True,True],[1,True,False],[True,True],[]])
def test_choice_receipt_changes_exactly_the_selected_boolean_cell(flags):
    with pytest.raises(ValueError):confirm_choice(choice_domain(SOURCE,ANSWER),0,{'game':{'remainingFlags':flags}})

@pytest.mark.parametrize('change',['missingwire','wrongmode','wrongfilter','wrongbound','wrongreturn','ambiguous'])
def test_client_array_policy_must_have_complete_current_mode_and_wire_proof(change):
    source=SOURCE
    if change=='missingwire':source=source.replace(WIRE,'')
    elif change=='wrongmode':source=source.replace('s.PICK="UNSEEN_CELLS"','s.PICK="OTHER_CELLS"')
    elif change=='wrongfilter':source=source.replace('0==e.remainingFlags','1==e.remainingFlags')
    elif change=='wrongbound':source=source.replace('i<e.remainingFlags.length','i<9')
    elif change=='wrongreturn':source=source.replace('t[0]},type','7},type')
    elif change=='ambiguous':source+=CONFIG
    with pytest.raises(ValueError):choice_domain(source,ANSWER)

@pytest.mark.parametrize('flags',[[0,1,0],[False,None,False],[True,True,True],[],[False]*33])
def test_server_array_must_be_bounded_boolean_and_have_unpicked_cells(flags):
    with pytest.raises(ValueError):choice_domain(SOURCE,{'game':{'nextMode':'UNSEEN_CELLS','remainingFlags':flags}})

def test_boolean_choice_index_must_be_an_integer_and_available():
    domain=choice_domain(SOURCE,ANSWER)
    for selected in [True,1,-1,3]:
        with pytest.raises(ValueError):confirm_choice(domain,selected,{'game':{'remainingFlags':[True,True,False]}})

def test_boolean_array_options_stay_stable_across_five_acknowledged_picks():
    flags=[False]*5
    for selected in range(5):
        answer={'game':{'nextMode':'UNSEEN_CELLS','remainingFlags':list(flags)}}
        domain=choice_domain(SOURCE,answer)
        assert domain['options']==list(range(5))
        assert domain['available']==list(range(selected,5))
        flags[selected]=True
        receipt={'game':{'mode':'UNSEEN_CELLS','nextMode':'FREESPIN' if all(flags) else 'UNSEEN_CELLS','remainingFlags':list(flags)}}
        confirm_choice(domain,selected,receipt)
        assert domain['before'][selected] is False
    assert flags==[True]*5

def test_boolean_array_domain_snapshot_does_not_alias_server_list():
    answer=copy.deepcopy(ANSWER)
    domain=choice_domain(SOURCE,answer)
    answer['game']['remainingFlags'][0]=True
    assert domain['before']==[False,True,False]
    assert domain['available']==[0,2]
