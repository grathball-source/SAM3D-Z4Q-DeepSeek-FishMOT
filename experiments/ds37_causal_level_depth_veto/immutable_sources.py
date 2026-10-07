"""Exact stdlib JSON bytes of immutable source samples; no scientific changes.

Profiling identified repeated serialization of the same complete source packet.
Only samples frozen recursively at creation can use cached bytes. Container and
engine changes are serialized afresh; public state/query copies stay mutable.
"""
import copy, hashlib, json
from functools import lru_cache

def _blocked(*args,**kwargs):raise RuntimeError('Immutable depth source payload')

class FrozenList(list):
    __setitem__=__delitem__=__iadd__=__imul__=append=extend=insert=pop=remove=clear=sort=reverse=_blocked
    def __deepcopy__(self,memo):return [copy.deepcopy(v,memo) for v in self]

class FrozenDict(dict):
    __slots__=('_encoded',)
    __setitem__=__delitem__=__ior__=clear=pop=popitem=setdefault=update=_blocked
    def __init__(self,value,cache=False):
        dict.__init__(self,((k,freeze(v)) for k,v in value.items()))
        object.__setattr__(self,'_encoded',encode(self) if cache else None)
    def __setattr__(self,*args):raise RuntimeError('Immutable depth source payload')
    def __deepcopy__(self,memo):return {copy.deepcopy(k,memo):copy.deepcopy(v,memo) for k,v in self.items()}

def freeze(value):
    if isinstance(value,dict):return FrozenDict(value)
    if isinstance(value,list):return FrozenList(freeze(v) for v in value)
    if isinstance(value,tuple):return tuple(freeze(v) for v in value)
    return value

def freeze_sample(value):return FrozenDict(value,cache=True)

def encode(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

@lru_cache(maxsize=10000)
def key_bytes(key):return encode(key)+b':'

def state_chunks(state):
    yield b'{'
    for i,key in enumerate(sorted(state)):
        if i:yield b','
        yield key_bytes(key)
        value=state[key]
        if key!='sample_pool':yield encode(value);continue
        yield b'{'
        for j,identifier in enumerate(sorted(value)):
            if j:yield b','
            yield key_bytes(identifier);sample=value[identifier]
            yield sample._encoded if isinstance(sample,FrozenDict) and sample._encoded is not None else encode(sample)
        yield b'}'
    yield b'}'

def digest_state(state):
    h=hashlib.sha256()
    for chunk in state_chunks(state):h.update(chunk)
    return h.hexdigest()

def digest_snapshot(snapshot):
    h=hashlib.sha256();h.update(b'{')
    for i,key in enumerate(sorted(snapshot)):
        if i:h.update(b',')
        h.update(key_bytes(key))
        if key=='evidence':
            for chunk in state_chunks(snapshot[key]):h.update(chunk)
        else:h.update(encode(snapshot[key]))
    h.update(b'}');return h.hexdigest()
