"""A client displayed remaining counter is independent of server aggregate totals."""
import hashlib
import math
import re
from functools import lru_cache
from .protocol import MAX_BODY


def counter_contract(source):
    """Return an independent snapshot of the exact client counter binding."""
    if not isinstance(source,str) or len(source)>MAX_BODY:return None
    proof=_counter_binding(source)
    if proof is None:return None
    return {'field':proof[0],'source_sha256':proof[1]}


@lru_cache(maxsize=2)
def _counter_binding(source):
    """Require the same game owner to supply the keypad's direct model counter."""
    if not isinstance(source,str) or len(source)>MAX_BODY:return None
    pattern=r'([\w$]+(?:\.[\w$]+)*)\.keypadPlugin\.setZeroBetSpinCounter\(\1\.model\.data\.([\w$]+)\)'
    fields={field for _,field in re.findall(pattern,source)}
    if len(fields)!=1:return None
    return next(iter(fields)),hashlib.sha256(source.encode('utf-8')).hexdigest()


def regular_counter(answer,source):
    """Select only the bound game counter; outer totals may include special spins."""
    contract=counter_contract(source)
    if contract is None:raise ValueError('Nolimit City: contador restante sin declaración cliente')
    return counter_from_contract(answer,contract)


def counter_from_contract(answer,contract):
    if (not isinstance(contract,dict) or not isinstance(contract.get('field'),str)
            or not re.fullmatch(r'[\w$]+',contract['field'])
            or not isinstance(contract.get('source_sha256'),str)
            or not re.fullmatch(r'[0-9a-f]{64}',contract['source_sha256'])):
        raise ValueError('Nolimit City: prueba de contador cliente inválida')
    game=answer.get('game') or {};field=contract['field'];value=game.get(field)
    if type(value) is float and math.isfinite(value) and value.is_integer() and 0<=value<=2**53-1:
        value=int(value)
    if type(value) is not int or value<0:raise ValueError('Nolimit City: contador restante cliente inválido')
    if 'freespinsLeft' in game and (type(game['freespinsLeft']) is not int or game['freespinsLeft']!=value):
        raise ValueError('Nolimit City: alias del contador cliente contradictorio')
    if 'remainingFreeSpins' in answer and (type(answer['remainingFreeSpins']) is not int or answer['remainingFreeSpins']<0):
        raise ValueError('Nolimit City: total de giros servidor inválido')
    return value
