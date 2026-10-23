"""Correlate nested NGM local client dispatches without guessing wire IDs.

A call is paired only with the response that closes its dispatcher stack frame,
inside the same browser frame/document. It is not a network receipt nor proof
of a settled bet; the independent ledger still verifies each spin and payout.
"""
from __future__ import annotations

class DispatchJournal:
    def __init__(self, max_pairs=2048, max_depth=32):
        self.max_pairs = max_pairs
        self.max_depth = max_depth
        self.stack = []
        self.pairs = []
        self._serial = 0

    def request(self, *, kind, frame, event_index, step=None, request_class=None):
        if (kind not in ('spin','continuation','round_metadata','state_save','round_finish',
                         'aux','unknown','unhandled_candidate') or
            not isinstance(frame,str) or not frame or len(frame)>300 or
            type(event_index) is not int or event_index<=0 or
            (step is not None and (type(step) is not int or step<0))):
            raise ValueError('NGM_DISPATCH_REQUEST_INVALID')
        if len(self.stack) >= self.max_depth or len(self.pairs)+len(self.stack)>=self.max_pairs:
            raise ValueError('NGM_DISPATCH_LIMIT')
        if request_class is not None and (not isinstance(request_class,str) or len(request_class)>120):
            raise ValueError('NGM_REQUEST_CLASS_INVALID')
        self._serial += 1
        pair = dict(dispatch_id=f'dispatch-{self._serial:06d}',kind=kind,
                    frame=frame,request_class=request_class,request_event=event_index,
                    response_event=None,step=step)
        self.stack.append(pair)
        return pair

    def response(self, *, frame, event_index):
        if not self.stack:
            raise ValueError('NGM_RESPONSE_WITHOUT_DISPATCH')
        pending = self.stack[-1]
        if frame != pending['frame']:
            raise ValueError('NGM_RESPONSE_WRONG_FRAME')
        if type(event_index) is not int or event_index<=pending['request_event']:
            raise ValueError('NGM_DISPATCH_RESPONSE_ORDER_INVALID')
        pending = self.stack.pop()
        pending['response_event'] = event_index
        self.pairs.append(pending)
        return pending

    def spins_in(self, start):
        if type(start) is not int or start <0 or start > len(self.pairs):
            raise ValueError('NGM_DISPATCH_START_INVALID')
        return [x for x in self.pairs[start:] if x['kind']=='spin']

    def verify_round(self, *, from_pair, expected_spins):
        if self.stack:
            raise ValueError('NGM_DISPATCH_UNCLOSED')
        spins=self.spins_in(from_pair)
        if (type(expected_spins) is not int or len(spins)!=expected_spins or
            [p['step'] for p in spins] != list(range(expected_spins))):
            raise ValueError('NGM_DISPATCH_SPIN_PAIR_MISMATCH')
        return spins

    def result(self, *, from_pair=0):
        return dict(schema='tester-spin/ngm-dispatch-journal/v1',
                    pairs=[dict(p) for p in self.pairs[from_pair:]],
                    open_dispatches=len(self.stack),
                    independent_round_ledger_required=True)
