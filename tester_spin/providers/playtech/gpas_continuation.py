"""Bounded, state-derived GPAS bonus continuation planning.

No network access. There is no pre-scripted count of free spins and no replay of
historical commands. Every step must be backed by the *latest* server response.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re

_PHASE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,79}\Z")


class ContinuationPlanner:
    def __init__(self, *, limit=200):
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError('INVALID_CONTINUATION_LIMIT')
        self.limit = limit
        self.visited = set()
        self.records = []

    def parameters(self, data, contract, picks):
        """Determine a next step without guessing an undisclosed pick index."""
        if not isinstance(data, dict) or not isinstance(contract, dict):
            raise ValueError('CONTINUATION_DATA_INVALID')
        phase = data.get('nextRound')
        if not isinstance(phase, str) or not _PHASE.fullmatch(phase) or phase == 'BET_END_STATE_IDENTIFIER':
            raise ValueError('CONTINUATION_STATE_UNKNOWN')
        if len(self.visited) >= self.limit:
            raise ValueError('ROUND_STEP_LIMIT')
        stack = data.get('playStack')
        if not isinstance(stack, list) or len(stack) > 128:
            raise ValueError('CONTINUATION_STAGE_UNBOUND')
        active = [s for s in stack if isinstance(s, dict) and s.get('round') == phase
                  and type(s.get('remainingPlayCount')) is int and s['remainingPlayCount'] > 0]
        if len(active) != 1:
            raise ValueError('CONTINUATION_STAGE_UNBOUND')
        stage = active[0]
        play_index = data.get('playIndex')
        remaining = stage['remainingPlayCount']
        mode = stage.get('modeType')
        if not isinstance(mode,str) or not _PHASE.fullmatch(mode):
            raise ValueError('CONTINUATION_STAGE_UNBOUND')
        offered = data.get('listPickPlayerPickOptions')
        if play_index is None and mode == 'LIST_PICK' and isinstance(offered, list) and offered:
            # Explicit selections supply a distinct server-advertised index
            # even on older client dialects without playIndex.
            play_index = -1
        elif type(play_index) is not int or play_index < 0:
            raise ValueError('CONTINUATION_PROGRESS_UNKNOWN')
        if mode == 'LIST_PICK' and offered is None and 'listPickPlayerPickOptions' not in data and phase == 'FreeGame':
            # GPAS FreeGame can use LIST_PICK for automatic free plays. If the
            # server declares a pending FreeGame but no pick domain, do not
            # invent a pick. Continue once with the normal zero-charge ID.
            # Fresh server proof, amount and final closure are still mandatory.
            params = []
            source = 'server-FreeGame-no-player-choice'
        elif mode == 'LIST_PICK':
            params = picks.parameters(data, contract.get('pick_bound') is True)
            if not params:
                raise ValueError('LIST_PICK_WITHOUT_SELECTED_OPTION')
            source = 'server-choice-domain'
        else:
            if offered not in (None, []):
                raise ValueError('UNHANDLED_CHOICES_FOR_STAGE')
            params = []
            source = 'server-stage-auto'
        marker = {'phase':phase,'mode':mode,'playIndex':play_index,
                  'remain':remaining,'parameters':params}
        digest = sha256(json.dumps(marker,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if digest in self.visited:
            raise ValueError('CONTINUATION_NO_PROGRESS')
        self.visited.add(digest)
        self.records.append({'phase':phase,'modeType':mode,'playIndex':play_index,
                             'remaining':remaining,'selection_source':source,
                             'chosen_options':[str(p['value']) for p in params],
                             'sequence':len(self.records)+1})
        return params
