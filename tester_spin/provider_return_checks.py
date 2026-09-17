"""Provider-specific closure callbacks. No cross-provider protocol inference."""
from tester_spin.return_to_base import save_exchange, verify_return_to_base


def rubyplay_check(runtime, directory, timeout_s, stop_event):
    from tester_spin.providers.rubyplay.runtime import post_action, validate_action_response

    def play(target):
        captures = []
        action = 'spin'
        had_event = False
        for step in range(1, 129):
            if stop_event.is_set():
                raise InterruptedError('Detención solicitada')
            response, request, data, previous_an = post_action(runtime, action, timeout_s=timeout_s, bet=runtime.default_bet)
            captures.append(save_exchange(target, request, data, step))
            warnings = validate_action_response(data, action=action, previous_an=previous_an)
            if warnings or response.status_code >= 400:
                return dict(ok=False, base=False, known=False, captures=captures, warnings=warnings)
            action = runtime.next_action
            if action == 'spin':
                return dict(ok=True, base=not had_event, known=True, captures=captures)
            had_event = True
            from tester_spin.providers.rubyplay.runtime_contracts import STATE_CONTINUATIONS, INDEX_CONTINUATIONS
            if action not in STATE_CONTINUATIONS - INDEX_CONTINUATIONS:
                return dict(ok=True, base=False, known=False, captures=captures, next_action=action)
        return dict(ok=True, base=False, known=False, captures=captures, reason='continuation limit')
    return verify_return_to_base(directory, play, stop_event=stop_event)


def redtiger_check(runtime, directory, timeout_s, stop_event):
    from tester_spin.providers.redtiger.execution import _post_spin
    from tester_spin.providers.redtiger.runtime import response_summary

    def play(target):
        status, request, data, warnings = _post_spin(runtime, stake=runtime.default_stake, feature_buy=None, timeout_s=timeout_s, stop_event=stop_event)
        capture = save_exchange(target, request, data)
        summary = response_summary(data)
        modes = {str(m).lower() for m in summary['spin_modes']}
        known = bool(summary['success']) and summary['pending_choice'] is None
        # The normal client mode is 0. Other returned modes are preserved for
        # review; success alone cannot prove a base spin.
        nodes = summary['nodes']
        inactive = bool(nodes) and all(node['has_state'] is False and node['feature_count'] == 0 for node in nodes)
        normal_mode = modes <= {'normal'} if modes else all(node['game_mode'] == 0 for node in nodes)
        base = known and inactive and normal_mode
        return dict(ok=status < 400 and not warnings, base=base, known=known and base,
                    captures=[capture], summary=summary)
    return verify_return_to_base(directory, play, stop_event=stop_event)


def bgaming_check(send, base_options, directory, stop_event, *, extra_data=None, legacy=False):
    from tester_spin.providers.bgaming.runtime import (
        legacy_safe_terminal_command, provider_error_envelope, flow_continuation_command,
    )

    def play(target):
        response, request, data = send('spin', options_payload=dict(base_options), extra_data_payload=extra_data)
        captures = []
        had_event = False
        for step in range(1, 257):
            captures.append(save_exchange(target, request, data, step))
            if response.status_code >= 400 or provider_error_envelope(data) is not None or data.get('error'):
                return dict(ok=False, base=False, known=False, captures=captures)
            if stop_event.is_set():
                raise InterruptedError('Detención solicitada')
            if legacy:
                flow = {'state': (data.get('game') or {}).get('state'), 'available_actions': data.get('available_commands')}
                command = legacy_safe_terminal_command(data)
            else:
                flow = data.get('flow') or {}
                command = flow_continuation_command(data)
            closed = flow.get('state') == 'closed' and 'spin' in (flow.get('available_actions') or [])
            if closed:
                return dict(ok=True, base=not had_event, known=True, captures=captures)
            # These commands have a demonstrated parameter-free continuation.
            # Advertised choices do not become executable just by being listed.
            if not command or (not legacy and command not in {'freespin', 'respin'}):
                return dict(ok=True, base=False, known=False, captures=captures,
                            pending_state=flow.get('state'), available_actions=flow.get('available_actions'))
            if step == 256:
                break
            had_event = had_event or not legacy
            response, request, data = send(command)
        return dict(ok=True, base=False, known=False, captures=captures, reason='continuation limit')
    return verify_return_to_base(directory, play, stop_event=stop_event)


def belatra_check(provider, state, directory, timeout_s, stop_event=None):
    def play(target):
        ok, terminal, steps, current, following = provider._execute_direct_spin(state, timeout_s=timeout_s, attempt_dir=target)
        import json
        captures = []
        for step, label in enumerate(('start', 'finish'), 1):
            req = target/f'{label}-request.json'
            resp = target/f'{label}-response.json'
            # Canonical Belatra filenames use a dot.
            if not req.exists():
                req, resp = target/f'{label}.request.json', target/f'{label}.response.json'
            if req.exists() and resp.exists():
                captures.append({'step': step, 'request': json.loads(req.read_text(encoding='utf-8')), 'response': json.loads(resp.read_text(encoding='utf-8'))})
        return dict(ok=ok, base=terminal, known=terminal, captures=captures, state=[current, following])
    return verify_return_to_base(directory, play, stop_event=stop_event)


def pragmatic_check(provider, bootstrap, last, base_fields, directory, timeout_s):
    current = dict(last)

    def play(target):
        nonlocal current
        captures = []
        had_event = False
        had_manual = False
        in_bonus = False
        action = 'doSpin'
        for step in range(128):
            from tester_spin.return_to_base import audit_stop_event
            stop = audit_stop_event()
            if stop is not None and stop.is_set():
                raise InterruptedError('Detención solicitada')
            fields = dict(base_fields)
            if action in {'doCollect', 'doBonus', 'doCollectBonus'}:
                fields = {key: fields[key] for key in ('symbol', 'repeat', 'mgckey') if key in fields}
            fields['action'] = action
            if action == 'doSpin':
                fields['bl'] = '0'
            fields.pop('pur', None)
            for key in ('index', 'counter'):
                fields[key] = str(int(current.get(key) or fields.get(key) or 0)+1)
            status, _, data, _ = provider._post_and_store(bootstrap, fields, target, step=step, label='base-check', timeout_s=timeout_s)
            captures.append(save_exchange(target, fields, data, step+1))
            current = data
            from tester_spin.providers.pragmatic_protocol import server_error
            err = server_error(data)
            if status >= 400 or err not in (None, '', '0'):
                return dict(ok=False, base=False, known=False, captures=captures)
            na = str(data.get('na') or '')
            active = provider._feature_active(data)
            from tester_spin.providers.pragmatic_reel_contract import reel_selection
            manual = reel_selection(data, getattr(bootstrap, 'reel_contract', None))
            had_manual = had_manual or manual is not None
            # A certified manual reel choice is part of the ordinary paid round.
            # Other features still reset consecutive normal-round confirmation.
            other_features = provider._feature_active({key:value for key,value in data.items()
                if key not in {'rs','rs_p','rs_c','rs_m'}})
            had_event = had_event or (active and (manual is None or other_features))
            if na == 'b':
                had_event = True
                in_bonus = True
                action = 'doBonus'
            elif na in {'cb', 'bc'} or (na == 'c' and in_bonus):
                action = 'doCollectBonus'
            elif na == 'c':
                action = 'doCollect'
            elif na == 's' and active:
                action = 'doSpin'
            elif (na == 's' or (not na and action in {'doCollect', 'doCollectBonus'})) and not active:
                return dict(ok=True, base=not had_event, known=True, captures=captures, manual_phase_observed=had_manual)
            else:
                return dict(ok=True, base=False, known=False, captures=captures, next_action=na)
        return dict(ok=True, base=False, known=False, captures=captures)
    return verify_return_to_base(directory, play)


def d1_check(provider, ws, frames, lines, bet_index, initial_state, directory, timeout_s):
    import time
    from tester_spin.return_to_base import audit_stop_event

    def play(target):
        nonlocal lines, bet_index
        captures = []
        had_event = False
        for step in range(1, 129):
            stop = audit_stop_event()
            if stop is not None and stop.is_set():
                raise InterruptedError('Detención solicitada')
            wire = provider._wire_message('1', f'{lines},{bet_index},0')
            ws.send(wire)
            frames.append({'direction': 'sent', 'classification': 'return-to-base' if step == 1 else 'return-continuation', 'payload': provider._frame_preview(wire)})
            deadline = time.monotonic()+max(2.0, timeout_s)
            payload = None
            while time.monotonic() < deadline:
                candidate = provider._recv_protocol_json(ws, deadline=deadline, frames=frames)
                message_type = provider._int_field(candidate.get('type'), -1)
                if message_type in {2, 3}:
                    payload = candidate
                    break
            if payload is None:
                raise TimeoutError('D1: sin respuesta a comprobación de regreso')
            captures.append(save_exchange(target, {'type': 1, 'lines': lines, 'bet_index': bet_index}, payload, step))
            if message_type == 2:
                return dict(ok=False, base=False, known=False, captures=captures)
            active = provider._d1_feature_active(payload)
            if active:
                had_event = True
                if payload.get('l') is not None:
                    lines = provider._int_field(payload['l'], lines)
                if payload.get('b3') is not None:
                    bet_index = provider._int_field(payload['b3'], bet_index)
                continue
            # Operational return is distinct from proving the st contract.
            same_state = payload.get('st') == initial_state and initial_state is not None
            terminal = getattr(provider, '_d1_result_terminal', lambda value: value.get('st') == 0)(payload)
            return dict(ok=True, base=(terminal or same_state) and not had_event,
                        known=terminal or same_state,
                        captures=captures, terminal_contract_proven=terminal)
        return dict(ok=True, base=False, known=False, captures=captures, reason='continuation limit')
    return verify_return_to_base(directory, play, observed_only=initial_state not in getattr(provider, 'D1_TERMINAL_STATES', {0}))
