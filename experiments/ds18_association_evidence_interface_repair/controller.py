"""DS18: measured sources are not identities; Birth proposals precede all writes.

Reuse the original candidate matrix, weights, timing and one-publication bridge.
Anonymous group/post sources retain measured scalars, but cannot certify clean
references or install a one-sided alias into a protected two-identity event.
"""
import copy
import importlib.util
import math
import sys
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
_spec = importlib.util.spec_from_file_location('ds18_reused_frozen_ds17_controller',
    ROOT/'experiments/ds17_mixed_depth_activity_repair/controller.py')
_ds17 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ds17)
_ds16 = _ds17._ds16
from px_z2 import BirthRefine, DepthRepair
if str(HERE) not in sys.path:
    sys.path.append(str(HERE))
import mixed_depth as _measure
assert Path(_measure.__file__).resolve()==HERE/'mixed_depth.py', 'wrong mixed_depth module namespace'
OriginalReturn, Bridge = _ds17.OriginalReturn, _ds17.Bridge
FrozenEventBridge, FrozenEventManager = _ds17.FrozenEventBridge, _ds17.FrozenEventManager
CLEAN_FIELDS, ACTIVITY_FIELDS = _ds17.CLEAN_FIELDS, _ds17.ACTIVITY_FIELDS
ANONYMOUS_CLASSES, EMPTY_CLEAN = _ds17.ANONYMOUS_CLASSES, _ds17.EMPTY_CLEAN
clean_reference, restore_clean = _ds17.clean_reference, _ds17.restore_clean


class PendingBirth(BirthRefine):
    # The copied frozen loop changes only the born set and pre-write evidence
    # gate. D1 receives the true first-seen table and its original timing rules.
    def step(self,frame,now,observations,profiles=None):
     profiles={} if profiles is None else profiles
     for n,p in profiles.items():assert p['frame']==frame and p['id']==n and p['mask']==f'n:{n}'
     obs=sorted(observations,key=lambda o:o['id']);native={o['id'] for o in obs};checks=[];events=[]
     born=self.birth_candidates(frame,now,obs) if self.first is not None else []
     if self.birth_enabled and born:
      self.birth_counts['births']+=sum(o['id'] not in self.birth for o in born)
      self.birth_counts['pending_evaluations']+=sum(o['id'] in self.birth for o in born)
      occupied={self.alias.get(n,{}).get('target',n) for n in native}
      current={self.alias.get(o['id'],{}).get('target',o['id']):o for o in obs};conflict=len(occupied)!=len(native)
      old=[];eligibility=[]
      for k,h in sorted(self.bank.items()):
       reasons=[]
       if k in occupied:reasons.append('occupied')
       if k in self.alias:reasons.append('alias_source')
       if h['clean_count']<5:reasons.append('insufficient_D1_history')
       if h['clean_time'] is None:reasons.append('no_D1_clean_anchor')
       elif now-h['clean_time']>12:reasons.append('D1_history_expired')
       if not 0<now-h['last_seen']<=6:reasons.append('not_recently_missing')
       if h['contact_time'] is None or h['last_seen']-h['contact_time']>1:reasons.append('no_recent_interaction')
       if not h['depth_history']:reasons.append('no_D1_depth_history')
       eligibility.append(dict(id=k,eligible=not reasons,failures=reasons,last_seen_age_s=now-h['last_seen'],clean_age_s=None if h['clean_time'] is None else now-h['clean_time'],clean_count=h['clean_count']))
       if not reasons:old.append(k)
      matrix=np.full((len(born),len(old)+len(born)),1e6);terms={}
      for i,o in enumerate(born):
       matrix[i,len(old)+i]=1.
       if conflict:
        checks.append(dict(native_id=o['id'],rejection='existing_alias_conflict_defer_to_D1',failures=['existing_alias_conflict_defer_to_D1'],evidence_max_frame=frame,old_eligibility=eligibility));continue
       for j,k in enumerate(old):
        t=self.edge(frame,now,o,k,profiles,occupied,current,{x['id'] for x in born},old);t['old_eligibility']=eligibility
        exclusion=self.edge_veto(frame,now,o,k,self.bank[k].get('anchor'),'BIRTH_REFINE')
        t['edge_veto']=exclusion
        if exclusion['veto']:
         t['failures'].append('pairwise_history_conflict');t['rejection']='pairwise_history_conflict'
         if self.pending.get(o['id'],{}).get('target')==k:self.pending.pop(o['id'],None)
        self.remember_birth(frame,now,o,k,t)
        checks.append(t)
        if not t['failures'] and t['cost'] is not None:matrix[i,j]=t['cost'];terms[i,j]=t
       if not old:checks.append(dict(native_id=o['id'],rejection='no_eligible_unoccupied_history',failures=['no_eligible_unoccupied_history'],evidence_max_frame=frame,old_eligibility=eligibility))
      rr,cc=linear_sum_assignment(matrix);total=float(matrix[rr,cc].sum());accepted=[]
      for i,j in zip(rr,cc):
       if j>=len(old) or matrix[i,j]>=1:continue
       alt=matrix.copy();alt[i,j]=1e6;ar,ac=linear_sum_assignment(alt);margin=float(alt[ar,ac].sum()-total);t=terms[i,j]
       if margin<self.birth_config['assignment_margin']:
        t['failures'].append('assignment_ambiguous');t['rejection']='assignment_ambiguous';continue
       t['assignment_margin']=margin;accepted.append((born[i],old[j],t))
      for o,k,t in accepted:
       n=o['id'];assert k not in occupied and n not in self.alias
       pending=self.pending_birth.get(n);original=self.birth.get(n,(frame,now))
       t.update(original_birth_frame=original[0],evaluation_frame=frame,public_at_frame=frame,source_previously_published=n in self.published_sources,pending_retry=pending is not None,
        actual_first_source_publication=copy.deepcopy(self.source_first_publication.get(n,dict(frame=frame,public_id=k))))
       self.pending_birth.pop(n,None)
       self.alias[n]=dict(target=k,anchor=copy.deepcopy(t['old_anchor']),commit_frame=frame)
       self.pending.pop(n,None);self.bank.pop(n,None);self.view_bank.pop(n,None);occupied.add(k)
       self.birth_counts['commits']+=1
       events.append(dict(kind='reconnect',origin_rule='BIRTH_REFINE',accepted=True,confirmations=1,birth_frame=original[0],confirmation_span_s=0.,extra_confirmation_frames=0,first_public_id=t['actual_first_source_publication']['public_id'],**copy.deepcopy(t)))
     areas_before={k:list(h['areas']) for k,h in self.bank.items()}
     ids,tr=DepthRepair.step(self,frame,now,obs)
     reset=set()
     for e in tr['events']:
      if e['kind']=='native_conflict_rollback':
       reset.update([e['native_id'],e['canonical_id']])
     for k in list(self.view_bank):
      if k not in self.bank or k in reset:self.view_bank.pop(k,None)
     occupied=set(ids.values())
     for o in obs:
      n=o['id'];k=ids[n];h=self.bank[k]
      if k in reset:continue
      previous_areas=areas_before.get(k,[])
      area_ref=float(np.median(previous_areas)) if previous_areas else float(o['area'])
      latent=any(q not in occupied and 0<=now-ts<=6 for q,ts in self.partners(h,k).items())
      common_clean=self.quality(o) and not o.get('neighbors') and .5*area_ref<=o['area']<=1.8*area_ref and not latent
      if not common_clean:continue
      a=dict(frame=frame,native_id=n,mask=o['mask'],canonical_id=k);p=profiles.get(n)
      for view in ['core','whole']:
       m=self.measurement(p,view)
       if m is None:continue
       oldview=self.view_bank.get(k,{}).get(view)
       count=1 if oldview is None or now-oldview['time']>self.birth_config['max_history_age_s'] else oldview['count']+1
       self.view_bank.setdefault(k,{})[view]=dict(m,anchor=copy.deepcopy(a),time=now,count=count)
     if self.birth_enabled:tr['events']=events+tr['events'];tr['birth_checks']=checks
     tr['pending_birth']=self.pending_birth_log(frame,now)
     assert len(set(ids.values()))==len(ids)==len(native)
     return ids,tr



class EventReturn(_ds17.EventReturn, PendingBirth):
    def __init__(self, config):
        super().__init__(config)
        self.evidence_frame = None
        self.certificates = {}
        self.source_versions = {}
        self.identity_versions = {}
        self.guarded = False
        self.reference_bindings = {}
        self.depth_history_bindings = {}
        self.ema_evidence = {}
        self.pending_birth = {}
        self.published_sources = set()
        self.source_first_publication = {}
        self.evidence_checks = []
        self.event_context = None
        self._active_anonymous = set()
        self._birth_edge_terms = {}
        self._step_observations = {}
        self._step_profiles = {}
        self._candidate_bindings = {}
        self._joint_certified_sources = set()

    def configure_evidence(self, frame, certificates, source_versions,
                           identity_versions=None, guarded=False):
        self.evidence_frame = frame
        self.certificates = copy.deepcopy(certificates)
        self.source_versions = copy.deepcopy(source_versions)
        self.identity_versions = copy.deepcopy(identity_versions or {})
        self.guarded = bool(guarded)

    def current_binding(self, native, role, stats, packet=None):
        packet = packet or (self._step_observations.get(native, {}) if role == 'D1_WHOLE'
                            else self._step_profiles.get(native, {}))
        binding = packet.get('measurement_bindings', {}).get(role)
        certificate = self.certificates.get(native)
        valid = bool(binding and certificate and native in self.source_versions
            and native in self.identity_versions and self.evidence_frame == self.observation_frame
            and _measure.validate_bound_measurement(binding, stats, role, certificate,
                source_version=self.source_versions.get(native),
                version_key=self.identity_versions.get(native), native=native,
                frame=self.evidence_frame)
            and binding['measurement_valid']
            and (not self.guarded or binding['screened_eligible']))
        return binding if valid else None

    @staticmethod
    def reference_key(public, role, anchor):
        return (public, role, anchor.get('native_id'), anchor.get('frame'), anchor.get('mask'))

    @staticmethod
    def normalized_matches(history, binding):
        scalar = binding['actual_scalar']
        return all(history.get(key) == scalar.get(raw) for key, raw in
                   (('z', 'median'), ('n', 'n'), ('fraction', 'valid_fraction'), ('mad', 'mad')))

    def bound_reference(self, public, role, history, frame):
        if not history or not history.get('anchor'):
            return None
        anchor = history['anchor']
        registered = self.reference_bindings.get(self.reference_key(public, role, anchor))
        if not registered or anchor.get('canonical_id') != public:
            return None
        binding, certificate = registered['binding'], registered['certificate']
        good = (_measure.validate_bound_measurement(binding, binding['actual_scalar'], role,
                    certificate, source_version=registered['source_version'],
                    version_key=registered['identity_version'], native=anchor['native_id'],
                    frame=anchor['frame'], before_frame=frame)
                and registered['public_id'] == public
                and binding['measurement_valid']
                and (not self.guarded or binding['screened_eligible']))
        if role != 'D1_WHOLE':
            good = good and self.normalized_matches(history, binding)
        return registered if good else None

    def history(self, public, view, frame, now):
        history = super().history(public, view, frame, now)
        role = 'BIRTH_CORE' if view == 'core' else 'BIRTH_WHOLE'
        if history is not None and self.bound_reference(public, role, history, frame) is None:
            self.evidence_checks.append(dict(frame=frame, role=role, public_id=public,
                anchor=copy.deepcopy(history['anchor']), status='UNKNOWN',
                reason='EXACT_OLD_ANCHOR_MEASUREMENT_BINDING_UNAVAILABLE'))
            return None
        return history

    def edge(self, frame, now, observation, public, profiles, occupied, current, born, old):
        terms = super().edge(frame, now, observation, public, profiles, occupied, current, born, old)
        unknown = []
        native = observation['id']
        for view, role in (('core', 'BIRTH_CORE'), ('whole', 'BIRTH_WHOLE')):
            if self.current_binding(native, role, profiles.get(native, {}).get(view, {}),
                                    profiles.get(native, {})) is None:
                unknown.append(f'query_{role}_binding')
        if terms['whole'] is None:
            unknown.append('target_whole_comparison')
        for partner in terms['partners']:
            if partner.get('candidate_whole') is None:
                unknown.append(f"partner_{partner['id']}_candidate_whole")
            if partner['active']:
                po = current[partner['id']]
                for view, role in (('core', 'BIRTH_CORE'), ('whole', 'BIRTH_WHOLE')):
                    if self.current_binding(po['id'], role, profiles.get(po['id'], {}).get(view, {}),
                                            profiles.get(po['id'], {})) is None:
                        unknown.append(f"partner_{partner['id']}_{role}_binding")
                if po['id'] in self._active_anonymous:
                    unknown.append(f"partner_{partner['id']}_identity_role_unresolved")
                for key in ('own_whole', 'cross_whole'):
                    if partner.get(key) is None:
                        unknown.append(f"partner_{partner['id']}_{key}")
        for competitor in terms['whole_other_candidates']:
            if competitor.get('excluded') != 'outside_motion_range' and competitor.get('comparison') is None:
                unknown.append(f"competitor_{competitor['id']}_whole")
        conflict = any('whole_explicit' in failure for failure in terms['failures'])
        terms['required_whole_evidence'] = dict(
            status='MEASURED_CONFLICT' if conflict else 'UNKNOWN' if unknown else 'QUALIFIED',
            unknown=unknown, policy='PER_CANDIDATE_UNKNOWN_NO_COMMIT_NO_ZERO_COST',
            sufficient=not unknown and not conflict)
        if unknown:
            terms['failures'].append('required_measurement_unknown')
            terms['rejection'] = terms['failures'][0]
        self._birth_edge_terms[native, public] = terms
        refs = terms['depth_anchors']
        evidence = dict(origin_rule='BIRTH_REFINE', evaluation_frame=frame,
            query={role:self.binding_fact(self.current_binding(native, role, profiles.get(native, {}).get(view, {}), profiles.get(native, {})))
                   for view,role in (('core','BIRTH_CORE'),('whole','BIRTH_WHOLE'))},
            target={role:self.reference_fact(public,role,refs.get(view),frame)
                    for view,role in (('core','BIRTH_CORE'),('whole','BIRTH_WHOLE'))},
            partners=[], competitors=[], required_whole=copy.deepcopy(terms['required_whole_evidence']))
        for partner in terms['partners']:
            q = partner['id']
            entry=dict(public_id=q, active=partner['active'],
                history={role:self.reference_fact(q,role,partner.get(f'{view}_history'),frame)
                         for view,role in (('core','BIRTH_CORE'),('whole','BIRTH_WHOLE'))})
            if partner['active']:
                pn=current[q]['id']
                entry.update(current_native=pn, current={role:self.binding_fact(self.current_binding(pn,role,profiles.get(pn,{}).get(view,{}),profiles.get(pn,{})))
                    for view,role in (('core','BIRTH_CORE'),('whole','BIRTH_WHOLE'))})
            evidence['partners'].append(entry)
        for competitor in terms['whole_other_candidates']:
            q = competitor['id']
            evidence['competitors'].append(dict(public_id=q, excluded=competitor.get('excluded'),
                whole=self.reference_fact(q,'BIRTH_WHOLE',self.view_bank.get(q,{}).get('whole'),frame)))
        self._candidate_bindings['BIRTH_REFINE',native,public] = evidence
        terms['association_evidence_sha256'] = _measure._digest(evidence)
        return terms

    @staticmethod
    def binding_fact(binding):
        return None if binding is None else copy.deepcopy(binding)

    def reference_fact(self, public, role, history, frame):
        registered = self.bound_reference(public,role,history,frame)
        return None if registered is None else {key:copy.deepcopy(registered[key])
            for key in ('public_id','anchor','binding','source_version','identity_version','committed_bridge_version')}

    def aggregate_evidence(self, public, frame):
        history=self.bank.get(public,{})
        contributions=[]
        valid=True
        for time,depth in history.get('depth_history',[]):
            record=self.depth_history_bindings.get(public,{}).get(time)
            binding=record.get('binding') if record else None
            good=bool(binding and record['median']==depth and record['clean_time']==time
                and binding['binding_sha256']==_measure._digest({k:v for k,v in binding.items() if k!='binding_sha256'})
                and binding['actual_scalar_sha256']==_measure._digest(binding['actual_scalar'])
                and binding['actual_scalar']['median']==depth and binding['association_role']=='D1_WHOLE'
                and binding['frame']==record['anchor']['frame']<frame
                and binding['native']==record['anchor']['native_id']
                and record['anchor']['canonical_id']==public
                and binding['source_version']==record['source_version']
                and binding['version_key']==record['identity_version']
                and binding['version_key'][3]==public
                and binding['certificate_sha256']==record['certificate_sha256']
                and binding['measurement_valid'] and (not self.guarded or binding['screened_eligible']))
            contributions.append(dict(time=time,depth_mm=depth,actual_contribution=copy.deepcopy(record),
                                      binding_integrity_valid=good))
            valid=valid and good
        ema=self.ema_evidence.get(public)
        ema_valid=bool(ema and ema['actual_ema_mm']==history.get('ema') and
            ema['actual_ema_mm']==(ema['input_median_mm'] if ema['previous_ema_mm'] is None else
                                  .2*ema['input_median_mm']+.8*ema['previous_ema_mm']))
        return dict(public_id=public,whole_history=contributions,actual_ema_mm=history.get('ema'),
            ema_last_update=copy.deepcopy(ema),complete=valid and ema_valid,
            aggregation='ORIGINAL_Z4Q_EMA_AND_LAST15_MAD_UNCHANGED',
            history_source_versions=[copy.deepcopy(record['actual_contribution'].get('source_version'))
                if record['actual_contribution'] else None for record in contributions])

    def edge_veto(self, frame, now, observation, public, anchor, origin_rule):
        native = observation['id']
        reasons = []
        spec = next(iter(self.protected.values()), None)
        if spec and public in spec['member_public']:
            reasons.append('WAIT_JOINT_GROUP_TRANSACTION')
        if native in self._active_anonymous:
            reasons.append('ANONYMOUS_IDENTITY_ROLE_NOT_ASSIGNABLE')
        if origin_rule == 'D1_DELAYED':
            if self.current_binding(native, 'D1_WHOLE', observation.get('depth', {}), observation) is None:
                reasons.append('QUERY_WHOLE_MEASUREMENT_UNKNOWN')
            history = self.bank.get(public)
            if self.bound_reference(public, 'D1_WHOLE', history, frame) is None:
                reasons.append('TARGET_WHOLE_ANCHOR_BINDING_UNKNOWN')
            aggregate=self.aggregate_evidence(public,frame)
            if not aggregate['complete']:
                reasons.append('TARGET_WHOLE_HISTORY_LINEAGE_UNKNOWN')
            # Current anonymous groups cannot serve as an individual reservation
            # witness for another source's D1 edge either.
            h = self.bank[public]
            evidence = dict(origin_rule='D1_DELAYED',evaluation_frame=frame,
                query=self.binding_fact(self.current_binding(native,'D1_WHOLE',observation.get('depth',{}),observation)),
                target_anchor=self.reference_fact(public,'D1_WHOLE',h,frame),
                **aggregate,partner_aggregates=[])
            for partner, contact in self.partners(h, public).items():
                ph = self.bank.get(partner)
                po = next((o for o in self._step_observations.values()
                           if self.alias.get(o['id'], {}).get('target', o['id']) == partner), None)
                included = (ph and ph['depth_history'] and ph['clean_time'] is not None
                            and now - ph['clean_time'] <= 6 and h['last_seen'] - contact <= 1)
                if included and partner!=native:
                    partner_evidence=self.aggregate_evidence(partner,frame)
                    evidence['partner_aggregates'].append(partner_evidence)
                    if not partner_evidence['complete']:
                        reasons.append(f'PARTNER_{partner}_WHOLE_HISTORY_LINEAGE_UNKNOWN')
                    latent=any(p!=public and p not in {
                        self.alias.get(n,{}).get('target',n) for n in self._step_observations}
                        and 0<=now-ts<=6 for p,ts in self.partners(ph,partner).items())
                    area_ref=float(np.median(ph['areas'])) if ph['areas'] else 0.
                    reservation_used=bool(po and not po.get('neighbors') and not latent
                        and area_ref>0 and .5*area_ref<=po['area']<=1.8*area_ref and self.quality(po)
                        and self.depth_valid(po) and ph['clean_count']>=5
                        and now-ph['clean_time']<=6 and abs(po['depth']['median']-self.z(ph))<=15)
                    partner_evidence['reservation_used']=reservation_used
                    if reservation_used:
                        partner_evidence['current_whole']=self.binding_fact(self.current_binding(
                            po['id'],'D1_WHOLE',po['depth'],po))
                        if partner_evidence['current_whole'] is None:
                            reasons.append(f'PARTNER_{partner}_RESERVATION_MEASUREMENT_UNKNOWN')
                if included and po and po['id'] in self._active_anonymous:
                    reasons.append(f'PARTNER_{partner}_IDENTITY_RESERVATION_UNKNOWN')
            self._candidate_bindings[origin_rule,native,public] = evidence
        pending = self.pending_birth.get(native)
        if origin_rule == 'BIRTH_REFINE' and pending:
            expected = pending['targets'].get(public)
            current = self.view_bank.get(public, {}).get('core', {}).get('anchor')
            if expected is None or expected != current:
                reasons.append('PENDING_TARGET_ANCHOR_CHANGED')
        check = dict(frame=frame, native_id=native, public_id=public, origin_rule=origin_rule,
            veto=bool(reasons), reason=reasons[0] if reasons else 'LEGAL_BOUND_CANDIDATE',
            reasons=reasons, measurement_identity_separated=True)
        evidence = self._candidate_bindings.get((origin_rule,native,public))
        if evidence is not None:
            check['association_evidence_sha256'] = _measure._digest(evidence)
        self.auto_edge_checks.append(check)
        return check

    def birth_candidates(self, frame, now, observations):
        result = []
        for observation in observations:
            native = observation['id']
            pending = self.pending_birth.get(native)
            if native not in self.birth:
                result.append(observation)
            elif pending and not pending.get('retired_reason') and native not in self.alias and native not in self.retired:
                unchanged = pending['source_version'] == self.source_versions.get(native)
                if self.event_context and pending.get('event_generation') not in (None, self.event_context['generation']):
                    unchanged = False
                first = self.birth[native]
                deadline = min(first[1] + 6, self.first_eligible.get(native, first[1] + 3) + 3)
                if unchanged and now <= deadline:
                    result.append(observation)
                else:
                    pending['retired_reason'] = ('SOURCE_GENERATION_CHANGED' if not unchanged
                                                  else 'ORIGINAL_BIRTH_WINDOW_EXPIRED')
        return result

    def remember_birth(self, frame, now, observation, public, terms):
        held = terms.get('edge_veto', {}).get('veto')
        unknown = terms.get('required_whole_evidence', {}).get('status') == 'UNKNOWN'
        if not held and not unknown:
            return
        # Keep original eligibility, candidate identity and exact reference.
        native = observation['id']
        first = self.birth.get(native, (frame, now))
        pending = self.pending_birth.setdefault(native, dict(original_birth_frame=first[0],
            original_birth_time=first[1], source_version=copy.deepcopy(self.source_versions.get(native)),
            targets={}, first_eligible_at_creation=self.first_eligible.get(native),
            event_generation=self.event_context['generation'] if self.event_context else None,
            first_proposal_frame=frame))
        if frame==pending['first_proposal_frame']:
            pending['targets'].setdefault(public, copy.deepcopy(self.view_bank.get(public, {}).get('core', {}).get('anchor')))
        pending.update(last_evaluation_frame=frame, last_reason=copy.deepcopy(terms.get('edge_veto')),
                       evidence_status=copy.deepcopy(terms.get('required_whole_evidence')))

    def pending_birth_log(self, frame, now):
        return {str(n): dict(copy.deepcopy(p), evaluation_frame=frame,
            true_birth=copy.deepcopy(self.birth.get(n)), actual_first_eligible=self.first_eligible.get(n),
            source_previously_published=n in self.published_sources,
            status='RETIRED' if p.get('retired_reason') else 'PENDING_NOT_IDENTITY_COMMIT')
            for n, p in self.pending_birth.items()}

    def register_committed_references(self, frame, mapping, epochs, bridge_version):
        for public, history in self.bank.items():
            anchor = history.get('anchor')
            if anchor and anchor['frame'] == frame:
                self.register_reference(public, 'D1_WHOLE', anchor, history, mapping, epochs, bridge_version)
            for view, value in self.view_bank.get(public, {}).items():
                if value['anchor']['frame'] == frame:
                    self.register_reference(public, 'BIRTH_CORE' if view == 'core' else 'BIRTH_WHOLE',
                        value['anchor'], value, mapping, epochs, bridge_version)
        for native, history in self.recent_core.items():
            if history['anchor']['frame'] == frame:
                self.register_reference(history['anchor']['canonical_id'], 'BIRTH_CORE', history['anchor'],
                    history, mapping, epochs, bridge_version)
        # Keep only actual current bank/view/recent anchors, not an unbounded frame archive.
        active = set()
        for public, history in self.bank.items():
            if history.get('anchor'):
                active.add(self.reference_key(public, 'D1_WHOLE', history['anchor']))
            for view, value in self.view_bank.get(public, {}).items():
                active.add(self.reference_key(public, 'BIRTH_CORE' if view == 'core' else 'BIRTH_WHOLE', value['anchor']))
        for history in self.recent_core.values():
            active.add(self.reference_key(history['anchor']['canonical_id'], 'BIRTH_CORE', history['anchor']))
        self.reference_bindings = {k: v for k, v in self.reference_bindings.items() if k in active}
        self.depth_history_bindings = {public: {time: record for time, record in records.items()
            if time in {t for t, _ in self.bank.get(public, {}).get('depth_history', [])}}
            for public, records in self.depth_history_bindings.items() if public in self.bank}
        self.ema_evidence = {k:v for k,v in self.ema_evidence.items() if k in self.bank}
        self.published_sources.update(mapping)
        for native,public in mapping.items():
            self.source_first_publication.setdefault(native,dict(frame=frame,public_id=public))

    def register_reference(self, public, role, anchor, history, mapping, epochs, bridge_version):
        native = anchor['native_id']
        if mapping.get(native) != public or native not in self.certificates:
            return
        if native in self._active_anonymous and native not in self._joint_certified_sources:
            return
        packet = self._step_observations.get(native, {}) if role == 'D1_WHOLE' else self._step_profiles.get(native, {})
        original = packet.get('measurement_bindings', {}).get(role)
        if original is None:
            return
        scalar = original['actual_scalar']
        # Withheld mixed scalars cannot be promoted from a hidden raw signature.
        compared = packet.get('depth', {}) if role == 'D1_WHOLE' else packet.get('core' if role == 'BIRTH_CORE' else 'whole', {})
        if self.current_binding(native, role, compared, packet) is None:
            return
        version = self.identity_versions.get(native)
        if version is None:
            return
        actual_version = list(version)
        actual_version[3:] = [public, epochs[native]]
        binding = _measure.bind_measurement(self.certificates[native], role, scalar,
            source_version=self.source_versions[native], version_key=actual_version)
        if role != 'D1_WHOLE' and not self.normalized_matches(history, binding):
            return
        self.reference_bindings[self.reference_key(public, role, anchor)] = _measure._freeze_facts(dict(
            public_id=public, anchor=copy.deepcopy(anchor), binding=binding,
            certificate=self.certificates[native],
            source_version=copy.deepcopy(self.source_versions[native]), identity_version=actual_version,
            committed_bridge_version=bridge_version))
        if role == 'D1_WHOLE':
            previous = self.ema_evidence.get(public)
            if previous and previous['time'] not in {t for t,_ in history['depth_history'][:-1]}:
                previous=None  # An actual legacy bank reset starts a new EMA lineage.
            self.depth_history_bindings.setdefault(public, {})[history['clean_time']] = _measure._freeze_facts(dict(
                median=binding['actual_scalar']['median'], binding_sha256=binding['binding_sha256'],
                certificate_sha256=binding['certificate_sha256'], source_version=copy.deepcopy(binding['source_version']),
                identity_version=actual_version, anchor=copy.deepcopy(anchor), binding=copy.deepcopy(binding),
                clean_time=history['clean_time'], committed_bridge_version=bridge_version))
            self.ema_evidence[public] = _measure._freeze_facts(dict(frame=anchor['frame'],time=history['clean_time'],
                previous_ema_mm=previous['actual_ema_mm'] if previous else None,
                previous_update_sha256=_measure._digest(previous) if previous else None,
                input_median_mm=binding['actual_scalar']['median'],actual_ema_mm=history['ema'],
                alpha=.2,previous_weight=.8,actual_input_binding=copy.deepcopy(binding),
                recurrence='FIRST_INPUT_ELSE_POINT2_CURRENT_POINT8_PREVIOUS_UNCHANGED',
                lineage_status='EACH_ACTUAL_CLEAN_UPDATE_RECORDED_BY_OWN_BRANCH_COMMIT'))

    def step(self, frame, now, observations, profiles=None):
        profiles = profiles or {}
        spec = next(iter(self.protected.values()), None)
        classes = (dict(self.observation_classes)
                   if self.observation_frame == frame else {})
        event_sources = set()
        if spec:
            event_sources = set(spec['member_sources']) | set(spec['suppressed'])
            for native in spec['suppressed']:
                classes.setdefault(native, 'GROUP_MEASUREMENT')
        anonymous = event_sources | {n for n, cls in classes.items() if cls in ANONYMOUS_CLASSES}
        public = set(spec['member_public']) if spec else set()
        # New pending sources can have their own native bank. It is not a clean
        # identity reference until the S0 transaction selects their mapping.
        public.update(self.alias.get(n, {}).get('target', n) for n in anonymous)
        before_clean = {k: clean_reference(self.bank.get(k, EMPTY_CLEAN)) for k in public}
        before_views = {k: copy.deepcopy(self.view_bank[k]) for k in public if k in self.view_bank}
        before_recent = {n: copy.deepcopy(self.recent_core[n]) for n in anonymous if n in self.recent_core}
        if spec:
            key = f"{spec['episode']}:{spec['generation']}"
            registry = self.identity_reference_registry.setdefault(key, dict(
                episode=spec['episode'], generation=spec['generation'],
                references={str(k): copy.deepcopy(before_clean[k]) for k in spec['member_public']},
                views={str(k): copy.deepcopy(before_views.get(k)) for k in spec['member_public']}))
            assert all(registry['references'][str(k)] == before_clean[k]
                       for k in spec['member_public']), 'certified event reference changed'
            assert all(registry['views'][str(k)] == before_views.get(k)
                       for k in spec['member_public']), 'certified event view provenance changed'
        self._active_anonymous = anonymous
        self._step_observations = {o['id']: o for o in observations}
        self._step_profiles = profiles
        self.evidence_checks = []
        self._joint_certified_sources = set()
        self._candidate_bindings = {}
        self._birth_edge_terms = {}
        ids, trace = _ds16.EventReturn.step(self, frame, now, observations, profiles)
        # The original step has advanced real activity, source continuity and
        # automatic transactions. Restore no activity or ownership fields.
        for k in public:
            if k not in self.bank:
                continue  # A valid source-bank retirement is not resurrection.
            restore_clean(self.bank[k], before_clean[k])
            self.view_bank.pop(k, None)
            if k in before_views:
                self.view_bank[k] = copy.deepcopy(before_views[k])
        for n in anonymous:
            self.recent_core.pop(n, None)
            if n in before_recent:
                self.recent_core[n] = copy.deepcopy(before_recent[n])
        for observation in observations:
            n = observation['id']
            cls = classes.get(n, 'SOURCE_OBSERVATION')
            if n in anonymous and cls == 'SOURCE_OBSERVATION':
                cls = 'UNRESOLVED_EVENT_OBSERVATION'
            self.source_activity[n] = _measure._freeze_facts(dict(frame=frame, time=now,
                observation_class=cls,
                identity_measurement_certified=(n not in anonymous and
                    self.bank.get(ids[n], {}).get('anchor', {}).get('frame') == frame),
                received_association_observation=copy.deepcopy(observation),
                received_association_profile=copy.deepcopy(profiles.get(n)),
                source_version=copy.deepcopy(profiles.get(n, {}).get('source_version', self.source_versions.get(n, 'UNKNOWN')))))
        activity = {str(k): {field: copy.deepcopy(self.bank[k].get(field)) for field in ACTIVITY_FIELDS}
                    for k in sorted(public) if k in self.bank}
        trace['activity_reference_separation'] = dict(
            protected_clean_fields=list(CLEAN_FIELDS), live_activity_fields=list(ACTIVITY_FIELDS),
            public_reference_keys=sorted(public), anonymous_native_keys=sorted(anonymous),
            public_activity=activity, missing_sources_not_updated=sorted(anonymous - set(ids)),
            certified_recent_core_frozen=sorted(anonymous),
            anonymous_current_measurement_preserved=sorted(anonymous & set(ids)),
            anonymous_identity_stage_separate=True,
            source_activity={str(n): copy.deepcopy(self.source_activity[n]) for n in sorted(anonymous & set(ids))})
        if spec:
            trace['activity_reference_separation']['immutable_reference_registry'] = copy.deepcopy(registry)
            trace['activity_reference_separation']['reference_status'] = {
                str(k): dict(
                    status=('LIVE_BANK_RETIRED' if k not in self.bank else
                        'NO_CERTIFIED_REFERENCE' if not self.bank[k].get('anchor') else
                        'REFERENCE_EXPIRED' if now - self.bank[k]['clean_time'] > 12 else
                        'UNCHANGED_CERTIFIED_REFERENCE'),
                    actual_bank_anchor=copy.deepcopy(self.bank.get(k, {}).get('anchor')),
                    actual_view_anchors={view: copy.deepcopy(value.get('anchor'))
                                        for view, value in self.view_bank.get(k, {}).items()},
                    actual_observed_alias_owners=[n for n, public_id in ids.items() if public_id == k])
                for k in spec['member_public']}
        if spec:
            spec['outputs'] = {n: ids[n] for n in spec['suppressed'] if n in ids}
            trace['merge_split_group'] = dict(episode=spec['episode'],
                suppressed=sorted(spec['suppressed']), outputs=copy.deepcopy(spec['outputs']),
                preview_only_not_published=True,
                publication_policy='OWN_BRANCH_CAUSAL_EVENT_ALIAS_OR_NATIVE',
                protected_public_banks_preserved=False,
                protected_clean_references_preserved=True,
                protected_identity_reference_stores=['bank.clean_fields', 'view_bank', 'recent_core'],
                source_proposal_lifecycle='ACTUAL_CURRENT_ORIGINAL_Z4Q_NOT_FROZEN',
                visible_source_state={str(n): dict(native_seen=self.native_seen.get(n),
                    native_run=copy.deepcopy(self.native_runs.get(n)),
                    recent_core_anchor=copy.deepcopy(self.recent_core.get(n, {}).get('anchor')))
                    for n in sorted(anonymous & set(ids))},
                depth_history_policy='GROUP_AND_UNASSIGNED_POST_REMAIN_ANONYMOUS')
        trace['association_evidence_checks'] = copy.deepcopy(self.evidence_checks)
        for action in trace['events']:
            if action.get('kind') == 'reconnect' and action.get('accepted'):
                action.setdefault('origin_rule','BIRTH_REFINE' if action.get('phase')=='birth' else 'D1_DELAYED')
                key=(action['origin_rule'],action['native_id'],action['canonical_id'])
                action['association_evidence_bindings'] = copy.deepcopy(self._candidate_bindings[key])
                action['association_evidence_sha256'] = _measure._digest(self._candidate_bindings[key])
        return ids, trace


class EventBridge(_ds17.EventBridge):
    def __init__(self, config):
        super().__init__(config)
        self.engine = EventReturn(config)

    def configure_evidence(self, frame, *, certificates, source_versions,
                           identity_versions=None, guarded=False):
        self.engine.configure_evidence(frame, certificates, source_versions, identity_versions, guarded)
        self.engine.observation_frame = frame

    def stage_group_restore(self, view, episode, selected):
        transaction, error = super().stage_group_restore(view, episode, selected)
        if transaction is not None:
            trial = transaction['engine']
            trial._joint_certified_sources = set(selected)
            for native in selected:
                trial.pending_birth.pop(native, None)
            transaction['trace']['ds18_joint_identity_commit'] = dict(
                selected=dict(selected), q=view['frame'], event_generation=episode['generation'],
                policy='ONLY_ORIGINAL_ATOMIC_TWO_POST_BIJECTION_CERTIFIES_EVENT_IDENTITIES')
        return transaction, error

    def commit_once(self, view, transaction=None):
        ids, trace = super().commit_once(view, transaction)
        self.engine.register_committed_references(view['frame'], ids, self.epochs, self.version)
        trace['ds18_reference_binding_state'] = dict(
            current_reference_count=len(self.engine.reference_bindings),
            history_population_count=sum(len(v) for v in self.engine.depth_history_bindings.values()),
            binding_registration='AFTER_ACTUAL_MAPPING_EPOCH_AND_ATOMIC_COMMIT',
            pending_birth= self.engine.pending_birth_log(view['frame'], view['now']),
            clean_whole_updates=[dict(public_id=public,
                **{k:copy.deepcopy(v) for k,v in evidence.items() if k!='actual_input_binding'},
                input_binding_sha256=evidence['actual_input_binding']['binding_sha256'],
                input_certificate_sha256=evidence['actual_input_binding']['certificate_sha256'],
                input_native=evidence['actual_input_binding']['native'],
                input_source_version=copy.deepcopy(evidence['actual_input_binding']['source_version']),
                input_identity_version=copy.deepcopy(evidence['actual_input_binding']['version_key']))
                for public,evidence in self.engine.ema_evidence.items() if evidence['frame']==view['frame']])
        return ids, trace


class EventManager(_ds17.EventManager):
    def before(self, row, profiles):
        result = super().before(row, profiles)
        episode = self.active
        self.bridge.engine.event_context = (dict(id=episode['id'], generation=episode['generation'],
            q=episode['q'], public_ids=list(episode['public_ids']),
            post_sources=list(episode['post_roles'])) if episode else None)
        return result

