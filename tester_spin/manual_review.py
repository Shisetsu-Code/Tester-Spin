"""Plain-language review list from saved results; no gameplay requests."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4


def _read(root, name):
    try:
        value = json.loads((root / name).read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def review_item(result):
    root = Path(result['run_dir']) if result.get('run_dir') else None
    observations = _read(root, 'server-observations.json') if root else {}
    tree = _read(root, 'run-tree.json') if root else {}
    attempts = result.get('attempts', [])
    modes = result.get('discovered_modes', [])
    details = ' '.join([str(result.get('error', ''))] + [str(a.get(k, '')) for a in attempts for k in ('error', 'warning')]).lower()
    reasons = []
    def add(reason, action):
        if (reason, action) not in reasons:
            reasons.append((reason, action))
    if not observations or not tree:
        add('Faltan registros para revisar esta prueba.', 'Repetir la prueba para completar el diagnóstico antes de preparar un HAR.')
    failed_modes = {str(a.get('mode_id', '')) for a in attempts if not a.get('ok') or not a.get('terminal') or a.get('error') or a.get('warning')}
    pending = [m for m in modes if m.get('executable') is False or m.get('observed') is False or 'UNRESOLVED' in str(m.get('kind', '')) or m.get('id') in failed_modes]
    if any('PURCHASE' in str(m.get('id', '')) or 'BUY' in str(m.get('id', '')) for m in pending) or 'compras anunciadas' in details or ('cobertura' in details and 'purchase_' in details):
        add('Hay compras o apuestas especiales pendientes.', 'Capturar cada compra y opción de apuesta especial disponible, incluida su finalización.')
    if 'contract_unresolved' in details or 'wire-shape de play' in details:
        add('Falta registrar cómo se hace la tirada normal.', 'Capturar la apertura del juego y dos tiradas normales.')
    if any(word in details for word in ('play_bonus', 'buy_extra_bonus', 'select_bonus', 'gamble', 'elecciones de flujo', 'todoubledialog')):
        add('Quedaron elecciones dentro del bonus sin completar.', 'Capturar el bonus y las opciones que ofrece; indicar cuál elegiste.')
    if 'bet devuelta' in details or 'balance inconsistente' in details or 'débito' in details:
        add('La apuesta o el saldo no coincide con lo esperado.', 'Capturar una tirada normal e indicar la apuesta mostrada y el saldo antes y después.')
    if any(word in details for word in ('httperror', 'http 4', 'http 5', 'rpc error', 'rpcerror')):
        add('El servidor rechazó una solicitud.', 'Repetir en el navegador la acción que falló y capturar su respuesta.')
    trajectories = tree.get('trajectories', [])
    if any(p.get('return_to_base') and p['return_to_base'].get('status') != 'CONFIRMED' for p in trajectories) or 'regreso al juego base pendiente' in details:
        add('No se confirmó el regreso al juego normal.', 'Completar el evento y continuar hasta lograr dos tiradas normales seguidas en la misma sesión.')
    if observations.get('unparsed') or any(o.get('review_required') for o in observations.get('observations', [])):
        add('Hay una respuesta distinta que debemos revisar.', 'Indicar qué apareció en pantalla y capturar cómo continuó el juego.')
    if result.get('status') == 'CANCELADO':
        add('La prueba se interrumpió.', 'Repetir la prueba antes de preparar un HAR.')
    if not reasons and (result.get('status') != 'OK' or pending or any(p.get('gaps') for p in trajectories)):
        add('La prueba quedó incompleta.', 'Capturar la acción pendiente y cómo se completa en el navegador.')
    if not reasons:
        return None
    labels = {'SPIN': 'tirada normal', 'PURCHASE_FREESPIN_BUY': 'compra de tiradas gratis',
              'PURCHASE_BONUS_BUY': 'compra de bonus', 'PURCHASE_BUY_BONUS': 'compra de bonus',
              'PURCHASE_FREESPIN_CHANCE': 'apuesta con mayor probabilidad de tiradas gratis',
              'PURCHASE_BONUS_CHANCE': 'apuesta con mayor probabilidad de bonus',
              'PURCHASE_FREESPIN_AND_BONUS_CHANCE': 'apuesta con mayor probabilidad de bonus y tiradas gratis'}
    actions = []
    for mid in sorted(failed_modes | {str(m.get('id', '')) for m in pending}):
        origin, _, selector = mid.partition('_MODE_')
        base, _, level = origin.partition('_LEVEL_')
        label = labels.get(base)
        if label:
            if level:
                label += f' (variante {level})'
            if selector:
                label += f' (modo {selector})'
            if label not in actions:
                actions.append(label)
    return {'name': ' '.join(result.get('game_name', result.get('slug', '')).split()),
            'provider': result.get('provider', ''), 'reasons': reasons, 'actions': actions}


def render_review(results, *, expected_count=None):
    rows = [r.to_dict() if hasattr(r, 'to_dict') else r for r in results]
    items = [item for row in rows if (item := review_item(row))]
    items.sort(key=lambda item: (item['provider'], item['name'].casefold()))
    lines = ['JUEGOS PARA REVISAR MANUALMENTE', '', f'{len(items)} juegos para revisar de {len(rows)} con resultado.']
    missing = max(0, (expected_count if expected_count is not None else len(rows)) - len(rows))
    if missing:
        lines.append(f'{missing} juegos sin resultado; falta ejecutarlos.')
    if not items:
        lines.append('No hay revisiones pendientes en los resultados disponibles.')
    else:
        lines += ['', 'Para el HAR: iniciar la captura antes de abrir el juego. Completar el evento y hacer dos tiradas normales seguidas sin cerrar la sesión.']
    for index, item in enumerate(items, 1):
        lines += ['', f"{index}. {item['name']} ({item['provider']})"]
        if item['actions']:
            lines.append('   Revisar: ' + '; '.join(item['actions']) + '.')
        for reason, action in item['reasons']:
            lines.append(f'   {reason} {action}')
    return '\n'.join(lines) + '\n'


def write_review(results, directory, *, expected_count=None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (datetime.now().strftime('%Y-%m-%d_%H-%M-%S') + '-' + uuid4().hex[:8] + '-revision-manual.txt')
    path.write_text(render_review(results, expected_count=expected_count), encoding='utf-8')
    return path
