"""A proposal uses the original lifecycle; rejection keeps the complete own preview."""
from common import *
import copy
from bridge import Bridge
from observer import branch_state

NATIVE_FIELDS = ('alias', 'birth', 'pending', 'native_seen', 'native_runs', 'recent_core',
                 'return_quarantine', 'empty_quarantine', 'first_eligible')
PUBLIC_FIELDS = ('bank', 'view_bank')

def outside_state(engine, natives, publics):
    return dict(native={f:{n:copy.deepcopy(v) for n,v in getattr(engine,f).items() if n not in natives} for f in NATIVE_FIELDS},
        public={f:{k:copy.deepcopy(v) for k,v in getattr(engine,f).items() if k not in publics} for f in PUBLIC_FIELDS},
        retired=engine.retired-natives)

class DepthBridge(Bridge):
    def stage_event(self, view, episode, selected):
        before = digest(branch_state(self)); preview = digest(dict(view, engine=vars(view['engine'])))
        transaction, error = self._stage_event(view, episode, selected)
        assert digest(branch_state(self)) == before and digest(dict(view, engine=vars(view['engine']))) == preview, 'stage mutated own state or preview'
        return transaction, error

    def _stage_event(self, view, episode, selected):
        if view['version'] != self.version or view['frame'] != episode['q']: return None, 'STALE_Q_SNAPSHOT'
        if set(selected) != set(episode['post_roles']) or set(selected.values()) != set(episode['public_ids']):
            return None, 'INVALID_COMPLETE_BIJECTION'
        local = {n:[s for s in values if s['frame'] <= view['frame']] for n,values in episode['post_roles'].items()}
        if any(len(v) != 1 or v[0]['frame'] != view['frame'] or v[0]['time'] != view['now'] or
               v[0]['source'] != n or v[0]['source_generation'] != episode['post_generations'][n] for n,v in local.items()):
            return None, 'ACTUAL_Q_SOURCE_OR_GENERATION_MISMATCH'
        sources = set(episode['member_sources']) | set(selected) | {episode['group_source']}
        targets = set(selected.values())
        # Do not revoke a latent/outside alias merely to make the proposal available.
        if any(n not in selected and a['target'] in targets for n,a in view['engine'].alias.items()):
            return None, 'UNSELECTED_OR_LATENT_ALIAS_OWNERSHIP'
        changes = {n:k for n,k in selected.items() if view['mapping'][n] != k}
        if not changes: return None, 'SELECTED_MAPPING_ALREADY_OWN_Z4Q'
        transaction, error = Bridge.stage(self, view, changes)
        if transaction is None: return None, error
        publics = targets | {view['mapping'][n] for n in changes} | set(changes)
        if outside_state(transaction['engine'], sources, publics) != outside_state(view['engine'], sources, publics):
            return None, 'OUTSIDE_EVENT_STATE_CHANGED'
        for n in changes:
            alias = transaction['engine'].alias.get(n)
            if alias: alias['source'] = 'DS35_RELIABLE_DEPTH_EVENT'
        transaction['trace'] = copy.deepcopy(transaction['trace'])
        transaction['trace']['ds35_depth_event'] = dict(event=episode['id'], selected=selected, changes=changes,
            evidence_pre_anchors={str(k):episode['bank_snapshot'][k]['anchor'] for k in targets},
            actual_lifecycle_past_anchors=transaction['anchors'],
            reference_semantics='Frozen independent pre is evidence; original lifecycle uses its actual current past bank; distinct anchors are recorded, not asserted identical.',
            actual_q_only_written=True, no_future_measurements_written=True, outside_state_preserved=True)
        return transaction, None

    def commit_once(self, view, transaction=None):
        result = Bridge.commit_once(self, view, transaction)
        if transaction:
            for n in transaction['changes']: self.provenance[n]['source'] = 'DS35_RELIABLE_DEPTH_EVENT'
        return result
