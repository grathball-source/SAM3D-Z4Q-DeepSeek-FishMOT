"""Original V4 episode rules plus finite, anonymous same-source post confirmation."""
import copy
from collections import defaultdict

from common import OLD, S0P, CFG, read
from manager_p import MergeSplitManagerP, OutputIdentityPolicy
from merge_split_manager import sample


class MergeSplitManager(MergeSplitManagerP):
    def __init__(self, arm, bridge, suspects, config=None, assignments=None):
        records = defaultdict(list)
        if isinstance(suspects, dict):
            for frame, hits in suspects.items():
                records[frame].extend(hits if isinstance(hits, list) else [hits])
        else:
            for hit in suspects: records[hit['frame']].append(hit)
        original = read(OLD / 'CONFIG_V7.json')
        original['max_episode_seconds'] = CFG['max_episode_seconds']
        super().__init__(arm, bridge, {f:v[0] for f,v in records.items()}, original, assignments)
        self.all_suspects = dict(records)
        self.scan_records = []
        self.release_episode = None
        self.close_reason = None

    def _release(self, episode, frame, status, current):
        # The runner must stage/commit this release before finish; no raw state copy.
        episode.update(status=status, release_frame=frame, release_reason=status, ready=False)
        self.release_episode = episode
        self.frame_class = {n:'UNRESOLVED_EVENT_OBSERVATION' for n in
            set(episode['member_sources']) | set(episode['post_roles']) | {episode['group_source']}}
        return dict(kind=status, episode=episode['id'], local_release_required=True)

    def _post_update(self, row, profiles, initial=False):
        episode = self.active
        current = {o['id']:o for o in row['observations']}
        sources = list(episode['post_roles'])
        if initial:
            episode['post_generations'] = {n:self._generation(n, row['frame']) for n in sources}
            episode['post_broken'] = False
            episode['consecutive_clean_post'] = 0
        broken = any(n not in current or self._generation(n, row['frame']) != episode['post_generations'][n] for n in sources)
        episode['post_broken'] |= broken
        clean = not episode['post_broken'] and all(self.bridge.engine.quality(current[n]) and
            not current[n].get('neighbors') and current[n]['area'] >= episode['minimum_restored_area'] for n in sources)
        if not initial:
            for n in sources:
                if n in current:
                    episode['post_roles'][n].append(sample(dict(current[n], frame=row['frame'], time=row['time']),
                        profiles.get(n), 'POST_UNASSIGNED', self._generation(n, row['frame'])))
        episode['consecutive_clean_post'] = episode['consecutive_clean_post'] + 1 if clean else 0
        episode['ready'] = episode['consecutive_clean_post'] >= CFG['confirmation_clean_frames']
        if episode['ready'] and 'confirmed_post_roles' not in episode:
            episode['confirmed_post_roles'] = {n:copy.deepcopy(values[-CFG['confirmation_clean_frames']:])
                                              for n,values in episode['post_roles'].items()}
        episode['evidence_cutoff_frame'] = row['frame']
        episode_timeout = row['time'] - episode['suspect_time'] > CFG['max_episode_seconds']
        episode['deadline_reached'] = episode_timeout or row['frame'] >= episode['q'] + CFG['lag_frames']
        self.close_reason = ('UNKNOWN_EPISODE_TIMEOUT' if episode_timeout else
            'UNKNOWN_POST_SOURCE_BREAK' if episode['post_broken'] else
            'UNKNOWN_DEADLINE_KEEP' if episode['deadline_reached'] and not episode['ready'] else None)
        episode['close_reason'] = self.close_reason
        self.frame_class = {n:'POST_UNASSIGNED' for n in sources}
        for n in episode['member_sources']:
            if n in current and n not in sources: self.frame_class[n] = 'ANONYMOUS_RESIDUAL'

    def before(self, row, profiles):
        self.release_episode = None
        self.close_reason = None
        hits = self.all_suspects.get(row['frame'], [])
        occupied = self.active is not None
        for index, hit in enumerate(hits):
            status = 'ACTIVE_EPISODE_OVERLAP' if occupied else 'SAME_FRAME_OVERLAP' if index else 'FIRST_RECORD_ATTEMPT'
            self.scan_records.append(dict(frame=row['frame'], record_index=index, status=status, suspect=copy.deepcopy(hit)))
            self.counts['scan/' + status] += 1
        if self.active is not None and self.active.get('q') is not None:
            self._post_update(row, profiles)
            episode = self.active
            spec = self.bridge.engine.protected[episode['id']]
            current = {o['id'] for o in row['observations']}
            outputs = {n:k for n,k in spec['outputs'].items() if n in current}
            for n in episode['post_roles']:
                if n in current and n not in outputs: outputs[n] = self._temporary_id(episode,n,row['frame'])
            spec['suppressed'] = list(outputs)
            spec['outputs'], _ = OutputIdentityPolicy.apply(episode, row, self.bridge.previous, self.last_source_frame, outputs)
            return dict(kind='POST_CONFIRMATION_PENDING', episode=episode['id'], ready=episode['ready'], close_reason=self.close_reason)
        signal = super().before(row, profiles)
        if self.active and self.active.get('q') == row['frame']:
            self._post_update(row, profiles, initial=True)
        if self.active:
            self.active.setdefault('ready', False)
            self.active.setdefault('post_broken', False)
        return signal

    def after(self, row, profiles):
        # Also invalidate a retained completed fragment when the active deque is empty.
        for n, history in list(self.last_clean.items()):
            if history and (history[-1]['source_generation'] != self._generation(n,row['frame']) or
                history[-1]['public_epoch'] != self.bridge.epochs.get(n) or
                history[-1]['public_id'] != self.bridge.previous.get(n)):
                self.last_clean.pop(n, None)
        super().after(row, profiles)

    def finish(self, frame, status):
        episode = self.active
        assert episode and frame >= (episode.get('q') or episode['suspect_frame'])
        episode.update(status=status, end=frame)
        self.bridge.engine.protected.pop(episode['id'], None)
        self.pending_clear.update(set(episode['member_sources']) | set(episode['post_roles']) | {episode['group_source']})
        self.active = self.release_episode = None
        self.close_reason = None


Manager = MergeSplitManager
EventManager = MergeSplitManager
