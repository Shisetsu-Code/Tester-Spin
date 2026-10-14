import pytest
from pathlib import Path
from tester_spin.providers.nolimit_city.choices import choice_domain,confirm_choice

STATIC='bonusGame:{options:()=>[{id:7},{id:9}],type:c.ASBonusPickOptions.PICK_MODE,pickNeededForModes:[g.Mode.BONUS_END]}'
AUTO='automaticPickGame:{optionSelection:t=>this.selectPick(t),type:c.ASBonusPickOptions.PICK_MODE,pickNeededForModes:[g.Mode.FS_PICK]} selectPick(t){let e=-1;for(;-1==e;){let i=M.randomIntInRange(0,2);-1==t.fsPicks[i]&&(e=i)}return e}'

def test_static_choice_ids_come_from_client_and_require_server_ack():
 answer={'game':{'nextMode':'BONUS_END','playerSelect':-1}}
 domain=choice_domain(STATIC,answer)
 assert domain['options']==[7,9] and domain['available']==[7,9]
 confirm_choice(domain,7,{'game':{'playerSelect':7}})
 with pytest.raises(ValueError):confirm_choice(domain,7,{'game':{'playerSelect':9}})

def test_server_array_supplies_unpicked_indices_without_guessing_a_domain():
 answer={'game':{'nextMode':'FS_PICK','fsPicks':[-1,2,-1]}}
 domain=choice_domain(AUTO,answer)
 assert domain['options']==[0,1,2] and domain['available']==[0,2]
 confirm_choice(domain,0,{'game':{'fsPicks':[4,2,-1]}})
 with pytest.raises(ValueError):confirm_choice(domain,0,answer)

def test_unadvertised_or_empty_choices_are_not_guessed():
 for source,answer in ((STATIC,{'game':{'nextMode':'OTHER','playerSelect':-1}}),(AUTO,{'game':{'nextMode':'FS_PICK','fsPicks':[1,2]}})):
  with pytest.raises(ValueError):choice_domain(source,answer)


def test_client_array_bounds_and_ack_shape_must_agree():
 answer={'game':{'nextMode':'FS_PICK','fsPicks':[-1,2,-1]}}
 with pytest.raises(ValueError):choice_domain(AUTO.replace('randomIntInRange(0,2)','randomIntInRange(0,1)'),answer)
 domain=choice_domain(AUTO,answer)
 with pytest.raises(ValueError):confirm_choice(domain,0,{'game':{'fsPicks':[4]}})
 with pytest.raises(ValueError):confirm_choice(domain,0,{'game':{'fsPicks':[4,3,-1]}})


def test_automatic_policy_without_complete_option_domain_is_not_a_collect_contract():
 source='automaticPickGame:{type:c.ASBonusPickOptions.PICK_MODE,optionSelection:()=>7,pickNeededForModes:["GAMBLE_FIFTY_FIFTY"]}'
 with pytest.raises(ValueError):choice_domain(source,{'game':{'nextMode':'GAMBLE_FIFTY_FIFTY','accumulatedRoundWin':10}})
