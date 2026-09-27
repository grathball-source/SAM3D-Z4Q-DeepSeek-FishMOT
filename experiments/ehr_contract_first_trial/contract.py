"""One frozen output contract for the prompt, examples, parser, and tests."""
import json

VERSION = 'EHR-CF-output-v1'
CHOICES = ('H1', 'H2', 'DEFER')
TOP = ('request_id', 'preferred_hypothesis', 'hypothesis_assessments', 'uncertainty_reason')
ASSESS = ('id', 'supporting_fact_ids', 'conflicting_fact_ids', 'unresolved_assumptions')
LISTS = ('supporting_fact_ids', 'conflicting_fact_ids', 'unresolved_assumptions')
ALIASES = ('id', 'hypothesis_id', 'hypothesis')
NORMALIZATIONS = ('single_label_alias_to_id', 'H1_H2_dictionary_to_list', 'assessment_order_H1_H2')


def schema():
    string_list = {'type': 'array', 'items': {'type': 'string'}}
    assessment = {'type': 'object', 'required': list(ASSESS), 'additionalProperties': False,
                  'properties': {'id': {'enum': ['H1', 'H2']},
                                 **{key: string_list for key in LISTS}}}
    return {'version': VERSION, 'type': 'object', 'required': list(TOP),
            'additionalProperties': False, 'properties': {
                'request_id': {'type': 'string'},
                'preferred_hypothesis': {'enum': list(CHOICES)},
                'hypothesis_assessments': {'type': 'array', 'minItems': 2, 'maxItems': 2,
                                            'uniqueIds': ['H1', 'H2'], 'items': assessment},
                'uncertainty_reason': {'type': 'string'}},
            'normalizations': list(NORMALIZATIONS)}


def example(choice):
    assert choice in CHOICES
    return {'request_id': 'SYNTHETIC_TEST_ONLY', 'preferred_hypothesis': choice,
            'hypothesis_assessments': [
                {'id': h, 'supporting_fact_ids': ['TEST-F1'] if h == choice else [],
                 'conflicting_fact_ids': ['TEST-F2'] if h != choice and choice != 'DEFER' else [],
                 'unresolved_assumptions': ['fixture ambiguity'] if choice == 'DEFER' else []}
                for h in ('H1', 'H2')],
            'uncertainty_reason': 'Fixture is ambiguous.' if choice == 'DEFER' else ''}


def system():
    task = ('Compare the two complete physical identity hypotheses in this causal event packet. '
            'A/B are qualified pre-risk fragments; X/Y are current q-local fragments. '
            'Use supplied measurements and actually sent images only. Anonymous observations or track handles during contact '
            'do not certify fish identity. A candidate path is a HYPOTHESIS, never an observed trajectory. '
            'Do not invent physical quantities, water-surface depth, fish heading from mask axis, unseen frames, probabilities, '
            'or tracker edits. Prefer DEFER if evidence cannot distinguish candidates. ')
    examples = [example(c) for c in CHOICES]
    return (task + 'Return JSON only. Output contract ' + VERSION + ': ' +
            json.dumps(schema(), separators=(',', ':'), ensure_ascii=False) +
            '. Each assessment must be one object in a two-element list with its own id H1 or H2. '
            'For a selected H, cite at least one actual supporting fact; for DEFER, give a nonempty uncertainty_reason. '
            'These three examples use TEST-F* fixture facts only; never cite them for any request: ' +
            json.dumps(examples, separators=(',', ':'), ensure_ascii=False))


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('DUPLICATE_JSON_KEY:' + key)
        result[key] = value
    return result


def _structure(obj, request_id):
    if not isinstance(obj, dict) or set(obj) != set(TOP) or obj.get('request_id') != request_id:
        return False
    if obj.get('preferred_hypothesis') not in CHOICES or not isinstance(obj.get('uncertainty_reason'), str):
        return False
    rows = obj.get('hypothesis_assessments')
    if not isinstance(rows, list) or len(rows) != 2 or not all(isinstance(x, dict) for x in rows):
        return False
    if not all(isinstance(x.get('id'), str) for x in rows) or {x['id'] for x in rows} != {'H1', 'H2'}:
        return False
    return all(set(row) == set(ASSESS) and
               all(isinstance(row[k], list) and all(isinstance(v, str) for v in row[k]) for k in LISTS)
               for row in rows)


def normalize(obj):
    """Only the three preregistered lossless container/key changes are allowed."""
    if not isinstance(obj, dict):
        return obj, [], 'NOT_OBJECT'
    out = dict(obj)
    rows = out.get('hypothesis_assessments')
    changes = []
    if isinstance(rows, dict):
        if set(rows) != {'H1', 'H2'} or not all(isinstance(v, dict) for v in rows.values()):
            return out, changes, 'INVALID_ASSESSMENT_DICTIONARY'
        converted = []
        for h in ('H1', 'H2'):
            row = dict(rows[h]); labels = [key for key in ALIASES if key in row]
            if len(labels) > 1 or (labels and row[labels[0]] != h):
                return out, changes, 'CONFLICTING_LABELS'
            if labels:
                row.pop(labels[0])
            converted.append({'id': h, **row})
        rows = converted
        changes.append(NORMALIZATIONS[1])
    elif isinstance(rows, list):
        rows = [dict(x) if isinstance(x, dict) else x for x in rows]
        for row in rows:
            if not isinstance(row, dict):
                return out, changes, 'NONOBJECT_ASSESSMENT'
            labels = [key for key in ALIASES if key in row]
            if len(labels) > 1:
                return out, changes, 'CONFLICTING_LABELS'
            if labels and labels[0] != 'id':
                row['id'] = row.pop(labels[0]); changes.append(NORMALIZATIONS[0])
    else:
        return out, changes, 'INVALID_ASSESSMENTS'
    if len(rows) != 2 or [x.get('id') for x in rows] not in (['H1', 'H2'], ['H2', 'H1']):
        return out, changes, 'DUPLICATE_OR_UNKNOWN_HYPOTHESIS'
    if rows[0]['id'] == 'H2':
        rows.reverse(); changes.append(NORMALIZATIONS[2])
    out['hypothesis_assessments'] = rows
    return out, list(dict.fromkeys(changes)), None


def visible_facts(packet):
    facts = set()
    def visit(value):
        if isinstance(value, dict):
            if isinstance(value.get('fact_id'), str):
                facts.add(value['fact_id'])
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(packet)
    table = packet.get('INTERACTION_TABLE')
    if table:
        index = table['columns'].index('fact_id')
        facts.update(row[index] for row in table['rows'])
    return facts


def parse(content, packet):
    result = dict(json_valid=False, decision_parseable=False, raw_choice=None,
                  strict_schema_valid=False, normalization_applied=[], normalized_schema_valid=False,
                  assessment_usable=False, fact_reference_valid=False, cited_fact_ids=[], errors=[])
    try:
        obj = json.loads(content, object_pairs_hook=_unique)
    except (TypeError, ValueError) as exc:
        result['errors'] = [str(exc) if 'DUPLICATE_JSON_KEY' in str(exc) else 'INVALID_JSON']
        return result
    result['json_valid'] = True
    if not isinstance(obj, dict):
        result['errors'] = ['NOT_OBJECT']; return result
    raw = obj.get('preferred_hypothesis')
    result['raw_choice'] = raw
    result['decision_parseable'] = raw in CHOICES
    result['strict_schema_valid'] = _structure(obj, packet['request_id'])
    normalized, changes, error = normalize(obj)
    result['normalization_applied'] = changes
    result['normalized_schema_valid'] = error is None and _structure(normalized, packet['request_id'])
    if not result['normalized_schema_valid']:
        result['errors'] = [error or 'INVALID_SCHEMA']; return result
    cited = [fact for row in normalized['hypothesis_assessments']
             for field in ('supporting_fact_ids', 'conflicting_fact_ids') for fact in row[field]]
    result['cited_fact_ids'] = cited
    unknown = [fact for fact in cited if fact not in visible_facts(packet)]
    result['fact_reference_valid'] = not unknown
    if unknown:
        result['errors'].append('UNKNOWN_FACT_ID')
    if raw in ('H1', 'H2') and not next(x for x in normalized['hypothesis_assessments'] if x['id'] == raw)['supporting_fact_ids']:
        result['errors'].append('NO_CHOSEN_SUPPORT')
    if raw == 'DEFER' and not normalized['uncertainty_reason'].strip():
        result['errors'].append('NO_DEFER_REASON')
    result['assessment_usable'] = not result['errors']
    return result
