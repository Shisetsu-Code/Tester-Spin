"""Reduced exact-version client bindings cross-checked against offline Aislador events."""
import copy
import json
from pathlib import Path

import pytest

from tester_spin.providers.nolimit_city.client_actions import automatic_command
from tester_spin.providers.nolimit_city.runtime import NolimitSession

FIXTURE = json.loads((Path(__file__).parent / "fixtures/nolimit_literal_automatic.json").read_text())
ACTION = {"type": "zeroBet", "bet": "0.00"}


@pytest.mark.parametrize("case", FIXTURE["cases"], ids=lambda case: case["phase"])
def test_literal_idle_binding_resolves_current_server_phase(case, tmp_path):
    session = NolimitSession()
    session.choice_client = FIXTURE["source"]
    assert session.choice_command(case["answer"], tmp_path, "SPIN") == ACTION
    assert session.pending_choice is None


@pytest.mark.parametrize("quote", [chr(34), chr(39)])
def test_literal_binding_matches_exact_unseen_phase_without_game_names(quote):
    source = 'e.Auto=class{start(t){n.Game.apiPlugin.betHandler.zeroBet(),t.finish()}};const P=new C.Auto;g.gameFlowController.addGameModeFlowStatePresentationMap('+quote+'UNSEEN_AUTO'+quote+',new Map([[l.FlowState.IDLE,P]]));'
    assert automatic_command(source, {"game": {"nextMode": "UNSEEN_AUTO"}}) == ACTION
    assert automatic_command(source, {"game": {"nextMode": "UNSEEN_AUT"}}) is None
    assert automatic_command(source.replace(quote+'UNSEEN_AUTO'+quote, 'phaseVariable'), {"game": {"nextMode": "UNSEEN_AUTO"}}) is None


@pytest.mark.parametrize("body", [
    'start(t){if(this.allowed)n.Game.apiPlugin.betHandler.zeroBet();t.finish()}',
    'start(t){const deferred=()=>n.Game.apiPlugin.betHandler.zeroBet();t.finish()}',
    'start(t){const tl=n.gsap.timeline({paused:true});tl.add(()=>n.Game.apiPlugin.betHandler.zeroBet())}',
    'start(t){t.finish()}history(){n.Game.apiPlugin.betHandler.zeroBet()}',
])
def test_literal_phase_never_substitutes_for_reachable_action_proof(body):
    source = 'e.Auto=class{'+body+'};const P=new C.Auto;g.gameFlowController.addGameModeFlowStatePresentationMap("UNSEEN_AUTO",new Map([[l.FlowState.IDLE,P]]));'
    assert automatic_command(source, {"game": {"nextMode": "UNSEEN_AUTO"}}) is None


def test_literal_phase_preserves_paid_extra_and_normal_rejections():
    case=FIXTURE["cases"][0]
    paid=copy.deepcopy(case["answer"])
    paid["game"]["extraSpinCost"]=1
    assert automatic_command(FIXTURE["source"], paid) is None
    assert automatic_command(FIXTURE["source"], {"game": {"nextMode": "NORMAL"}}) is None
