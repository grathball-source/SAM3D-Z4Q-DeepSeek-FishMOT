"""Immutable pre-risk fragments, anonymous risk facts and first-ever births."""
import copy
from common import HERE,read
from merge_split_manager import sample
CFG=read(HERE/'CONFIG.json')

class BirthMemory:
    def __init__(self,segment):
        self.segment=segment
        self.first_seen={};self.disappeared={};self.live={};self.anchor_versions={}

    def after(self,row,profiles,manager,raw_state,ids,classes,measurements=None):
        """Record only committed current facts; never insert a query into old pre."""
        branch=manager.bridge
        for o in row['observations']:
            n=o['id'];f=row['frame'];public=ids[n]
            key=[self.segment,raw_state.arm,manager._generation(n,f),public,branch.epochs[n]]
            record=self.live.get(n)
            if not record or record['key']!=key or record['last_frame']!=f-1:
                record=dict(key=key,current=[],geometry_history=[],samples=[],reference_anchor=None,
                    risk_observations=[],last_frame=None,last_time=None)
                self.live[n]=record
            state=raw_state.live.get(n)
            raw_clean=bool(state and list(state['key'])==key and state['samples'] and
                state['samples'][-1]['frame']==f and classes[n]=='SOURCE_OBSERVATION')
            p=sample(dict(o,frame=f,time=row['time']),profiles.get(n),classes[n],key[2],public,key[4])
            if raw_clean:
                if not record['current']:
                    record['geometry_history']=[];record['samples']=[]
                record['current'].append(p)
                record['current']=record['current'][-CFG['history_frames']:]
                record['geometry_history']=copy.deepcopy(record['current'])
                actual={s['frame']:s for s in state['samples']}
                record['samples']=[dict(copy.deepcopy(actual[x['frame']]),version_key=key,
                    source_native=n) for x in record['current']]
                record['reference_anchor']=dict(frame=f,time=row['time'],native_id=n,mask=o['mask'],
                    canonical_id=public,source_generation=key[2],public_epoch=key[4])
                record['risk_observations']=[]
            else:
                record['current']=[]
                fact=(measurements or {}).get(n)
                if fact is None and state and state['cache'] and state['cache'][-1]['frame']==f:
                    fact=state['cache'][-1]['measurement']
                record['risk_observations'].append(dict(frame=f,time=row['time'],
                    anonymous_token=f'F{f}/source:{n}',source_native=n,
                    observation_class=classes[n],bbox=list(o['box']),area=o['area'],
                    neighbors=list(o.get('neighbors',[])),version_key=key,
                    source_generation=key[2],public_epoch=key[4],
                    raw_fact_id=fact.get('fact_id') if fact else None,
                    raw_core_usable=bool(fact and fact['core_usable']),identity_continuity='UNKNOWN'))
            record['last_frame'],record['last_time']=f,row['time']
            anchor=branch.engine.bank.get(public,{}).get('anchor')
            if anchor and anchor['frame']==f and anchor['native_id']==n:
                self.anchor_versions[(public,n,f)]=copy.deepcopy(key)

    def before(self,row,profiles,manager,raw_state,view):
        branch=manager.bridge
        current={o['id']:o for o in row['observations']}
        for native in set(branch.previous)-set(current):
            public=branch.previous[native];record=self.live.get(native)
            raw=raw_state.live.get(native);anchor=copy.deepcopy(branch.engine.bank.get(public,{}).get('anchor'))
            key=copy.deepcopy(record['key']) if record else None
            anchor_key=(public,anchor['native_id'],anchor['frame']) if anchor else None
            self.disappeared[native]=dict(public=public,source=native,
                disappearance_frame=row['frame'],last_seen_frame=record['last_frame'] if record else None,
                last_seen_time=record['last_time'] if record else None,
                epoch=branch.epochs.get(native),generation=manager.source_generation.get(native),
                anchor=anchor,bank_anchor_version=copy.deepcopy(self.anchor_versions.get(anchor_key)),
                reference_anchor=copy.deepcopy(record['reference_anchor']) if record else None,
                geometry_history=copy.deepcopy(record['geometry_history']) if record else [],
                frozen_depth=dict(key=key,samples=copy.deepcopy(record['samples']) if record else [],
                    source=native,public=public,cutoff_frame=row['frame']-1,acquired_interval_seconds=None),
                anonymous_risk_observations=copy.deepcopy(record['risk_observations']) if record else [],
                last_raw_was_clean=bool(raw and raw['samples'] and
                    raw['samples'][-1]['frame']==(record['last_frame'] if record else None)))
        for native in current:self.disappeared.pop(native,None)
        queries=[]
        for native,observation in sorted(current.items()):
            if native in self.first_seen:continue
            self.first_seen[native]=row['frame']
            query=sample(dict(observation,frame=row['frame'],time=row['time']),profiles.get(native),
                'BIRTH_UNASSIGNED',manager._generation(native,row['frame']),view['mapping'][native],
                view['epochs'].get(native))
            query['quality']=branch.engine.quality(observation)
            candidates=[]
            for candidate in sorted(self.disappeared.values(),key=lambda c:(c['public'],c['source'])):
                c=copy.deepcopy(candidate);reasons=[]
                h=c['geometry_history'];d=c['frozen_depth'];ss=d['samples']
                expected=[self.segment,raw_state.arm,c['generation'],c['public'],c['epoch']]
                if c['anchor'] is None:reasons.append('NO_PAST_BANK_ANCHOR')
                elif (branch.engine.bank.get(c['public'],{}).get('anchor')!=c['anchor'] or
                      c['anchor'].get('native_id')!=c['source'] or c['anchor']['frame']>=row['frame'] or
                      c['bank_anchor_version']!=expected):
                    reasons.append('EXACT_BANK_SOURCE_ANCHOR_OR_VERSION_INVALID')
                if c['public'] in view['mapping'].values():reasons.append('CURRENT_PUBLIC_OCCUPIED')
                if any(a['target']==c['public'] for a in branch.engine.alias.values()):reasons.append('PUBLIC_ALIAS_CLAIMED')
                if any(c['public'] in p['member_public'] for p in branch.engine.protected.values()):reasons.append('GROUP_PUBLIC_RESERVED')
                if (len(h)<CFG['birth_min_history_samples'] or
                    any(p['source']!=c['source'] or p['public_id']!=c['public'] or
                        p['public_epoch']!=c['epoch'] or p['source_generation']!=c['generation'] or
                        p.get('neighbors') or p['area']<64 or p['observation_class']!='SOURCE_OBSERVATION' for p in h) or
                    any(b['frame']!=a['frame']+1 or b['time']<=a['time'] for a,b in zip(h,h[1:]))):
                    reasons.append('NO_CONTIGUOUS_SAME_VERSION_PRE_RISK_GEOMETRY')
                if (d['key']!=expected or len(ss)<CFG['birth_min_history_samples'] or not h or
                    [s['frame'] for s in ss]!=[p['frame'] for p in h] or
                    any(b['frame']!=a['frame']+1 or b['time']<=a['time'] for a,b in zip(ss,ss[1:]))):
                    reasons.append('NO_JOINT_SENSOR_CERTIFIED_PRE_RISK_DEPTH')
                if not ss or not 0<row['time']-ss[-1]['time']<=CFG['birth_max_gap_seconds']:
                    reasons.append('FULL_PRE_RISK_GAP_OUTSIDE_FIXED_12_SECONDS')
                c['risk_interval']=dict(reference_frame=ss[-1]['frame'] if ss else None,
                    reference_time=ss[-1]['time'] if ss else None,last_appearance_frame=c['last_seen_frame'],
                    disappearance_frame=c['disappearance_frame'],query_frame=row['frame'],query_time=row['time'],
                    full_gap_seconds=row['time']-ss[-1]['time'] if ss else None,
                    observed_risk_frames=[p['frame'] for p in c['anonymous_risk_observations']],
                    missing_interval_frames=[c['disappearance_frame'],row['frame']-1],
                    identity_continuity='UNKNOWN',path_between_reference_and_query='UNOBSERVED_NOT_INTERPOLATED')
                c.update(eligible=not reasons,reasons=reasons,query_cutoff_frame=row['frame'])
                candidates.append(c)
            queries.append(dict(source=native,first_source_frame=row['frame'],query_observation=query,
                candidates=candidates,post_sample_count=1))
        return queries
