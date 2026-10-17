"""Retained shot proposals and advisory continuity reviews, not canonical edits."""
from __future__ import annotations

import json
import math
import re
import uuid
from pathlib import Path

from .creation import _commit, content_digest, load_creation
from .creation_review import _text, inception_source_digest
from .continuity import ledger
from .errors import PermissionDeniedError, ResourceNotFoundError, RevisionConflictError, ValidationError
from .events import Event, append_event
from .project import load_production
from .state import Actor, now, scene_lock

BASES = ('authored', 'computed', 'inferred', 'unknown')
VERDICTS = ('ready_for_human', 'needs_changes', 'inconclusive')


def _projection(production):
    fields = ('id', 'title', 'summary', 'direction', 'script', 'cast', 'location', 'style', 'geometry',
              'continuity', 'findings', 'avoid', 'shots')
    return {**{key: production.get(key) for key in ('id', 'title', 'logline', 'cast', 'looks', 'sequences')},
            'scenes': [{key: item.get(key) for key in fields} for item in production['scenes']]}


def planning_digest(root, state=None, production=None):
    state = load_creation(root) if state is None else state
    production = load_production(root) if production is None else production
    # Round-trip Path-like operational values without exposing the host's project root.
    public = json.loads(json.dumps(_projection(production), default=str))
    return content_digest({'creative_material': inception_source_digest(root, state), 'production': public})


def planning_context(root: Path):
    root = Path(root).resolve(); production = load_production(root); state = load_creation(root)
    evidence = {}
    public = json.loads(json.dumps(_projection(production), default=str))
    for scene in public['scenes']:
        evidence['scene:' + scene['id']] = {'basis': 'authored', 'scene': scene['id'],
                                          'description': 'Canonical scene/shot declarations; computed fields are marked separately.'}
        for finding in scene.get('findings') or []:
            evidence['check:' + content_digest(finding)[:16]] = {'basis': 'computed', 'finding': finding}
    report = ledger(production)
    public_ledger = {**report, 'findings': {key: [finding.public_dict() for finding in findings]
                                           for key, findings in report['findings'].items()}}
    for findings in public_ledger['findings'].values():
        for finding in findings:
            evidence['check:' + content_digest(finding)[:16]] = {'basis': 'computed', 'finding': finding}
    evidence['continuity:ledger'] = {'basis': 'computed', 'description': 'Existing declared continuity ledger, not pixel inspection.'}
    return {'project_id': production['id'], 'revision': state['revision'],
            'planning_digest': planning_digest(root, state, production), 'production': public,
            'continuity': public_ledger, 'evidence': evidence,
            'art_briefs': state.get('art_briefs', []),
            'direction_plans': state.get('direction_plans', []),
            'continuity_reviews': state.get('continuity_reviews', []),
            'human_directions': state.get('assessment_decisions', [])[-6:]}


def _scene(context, scene_id):
    scene = next((item for item in context['production']['scenes'] if item['id'] == scene_id), None)
    if scene is None:
        raise ResourceNotFoundError('No canonical scene with that id')
    return scene


def _facts(items):
    if not isinstance(items, list) or len(items) > 30:
        raise ValidationError('Entry/exit facts must be a list of at most 30 subject/attribute/value records')
    keys = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValidationError('A proposed fact must be a structured record')
        for key in ('subject', 'attribute', 'value'):
            _text(item.get(key), 'proposed ' + key, 500)
        identity = (item['subject'], item['attribute'])
        if identity in keys:
            raise ValidationError('A proposed state cannot give two values to one fact')
        keys.add(identity)
    return {(item['subject'], item['attribute']): item['value'] for item in items}


def _plan_fields(title, intention, shots):
    _text(title, 'plan title', 240); _text(intention, 'directing intention', 4000)
    if not isinstance(shots, list) or not 1 <= len(shots) <= 32:
        raise ValidationError('Propose 1 to 32 ordered shots per scene')
    ids = set()
    for shot in shots:
        if not isinstance(shot, dict) or not isinstance(shot.get('id'), str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', shot['id']):
            raise ValidationError('Each proposal needs a local shot id')
        if shot['id'] in ids:
            raise ValidationError('Proposal shot ids must be distinct')
        ids.add(shot['id'])
        for key in ('label', 'action', 'framing', 'camera_intent'):
            _text(shot.get(key), key, 2000)
        duration = shot.get('duration_seconds')
        if type(duration) not in (int, float) or not math.isfinite(duration) or not 0 < duration <= 600:
            raise ValidationError('A proposed shot duration must be finite and between 0 and 600 seconds')
        units = shot.get('script_units')
        if not isinstance(units, list) or not units or any(type(unit) is not int for unit in units) or len(set(units)) != len(units):
            raise ValidationError('Each shot must pin distinct screenplay unit indices')
        for key in ('state_in', 'state_out'):
            _facts(shot.get(key))
        for key in ('existing_shot', 'transition_intent'):
            if not isinstance(shot.get(key, ''), str) or len(shot.get(key, '')) > 2000:
                raise ValidationError(key + ' must be bounded text')


def plan_checks(plan, context):
    """Computed checks concern the proposal, never invented physical geometry."""
    scene = _scene(context, plan['scene']); units = (scene.get('script') or {}).get('units', [])
    covered = {index for shot in plan['shots'] for index in shot['script_units']}
    checks = []
    for unit in units:
        if unit['kind'] == 'speech' and unit['index'] not in covered:
            checks.append({'code': 'proposed_dialogue_uncovered', 'severity': 'warning',
                           'evidence': f"Screenplay unit {unit['index']} has no proposed shot: {unit['text']}"})
    row = next(item for item in context['continuity']['scenes'] if item['id'] == plan['scene'])
    for (subject, attribute), value in _facts(plan['shots'][0]['state_in']).items():
        declared = row['at_start'].get(subject, {}).get(attribute)
        if declared and declared['value'] != value and not plan['shots'][0].get('transition_intent', '').strip():
            checks.append({'code': 'proposed_scene_start_conflict', 'severity': 'warning',
                           'evidence': f"{subject} {attribute} is declared {declared['value']!r}, not proposed {value!r}."})
    for previous, incoming in zip(plan['shots'], plan['shots'][1:]):
        before, after = _facts(previous['state_out']), _facts(incoming['state_in'])
        for key in before.keys() & after.keys():
            if before[key] != after[key] and not incoming.get('transition_intent', '').strip():
                checks.append({'code': 'proposed_state_jump', 'severity': 'warning',
                    'evidence': f"{previous['id']} -> {incoming['id']}: {key[0]} {key[1]} changes from {before[key]!r} to {after[key]!r} without transition intent."})
    return checks


def _checked(root, revision, digest):
    state = load_creation(root)
    if type(revision) is not int or revision < 0:
        raise ValidationError('expected_revision must be a non-negative integer')
    if state['revision'] != revision:
        raise RevisionConflictError(revision, state['revision'])
    context = planning_context(root)
    if not digest or digest != context['planning_digest']:
        raise ValidationError('Planning sources changed; reread scene/continuity before publishing')
    return state, context


def _append(root, state, key, record, actor):
    if actor.kind != 'agent':
        raise PermissionDeniedError('Shot proposals and continuity findings are agent work, not human approvals')
    changed = {**state, 'revision': state['revision'] + 1, key: [*state.get(key, []), record]}
    _commit(root, changed)
    append_event(root, Event.create('creation.' + key, state['project_id'], record_id=record['id'],
                                   revision=changed['revision'], actor=actor.public_dict()))
    return {'revision': changed['revision'], 'record': record}


def save_direction_plan(root: Path, *, scene, title, intention, shots, expected_revision,
                        expected_planning_digest, actor: Actor, based_on='', art_brief=''):
    _plan_fields(title, intention, shots); root = Path(root).resolve()
    with scene_lock(root):
        state, context = _checked(root, expected_revision, expected_planning_digest)
        canonical = _scene(context, scene)
        if not (canonical.get('script') or {}).get('linked'):
            raise ValidationError('Link this canonical scene to its screenplay before shot planning')
        known_units = {unit['index'] for unit in canonical['script']['units']}
        known_shots = {shot['id'] for shot in canonical['shots']}
        for shot in shots:
            if any(index not in known_units for index in shot['script_units']):
                raise ValidationError('A proposed shot names a nonexistent screenplay unit')
            if shot.get('existing_shot') and shot['existing_shot'] not in known_shots:
                raise ValidationError('The associated canonical shot does not belong to this scene')
        if based_on and not any(item['id'] == based_on and item['scene'] == scene for item in state.get('direction_plans', [])):
            raise ValidationError('A proposal revision must refer to an existing plan of the same scene')
        art = next((item for item in state.get('art_briefs', []) if item['id'] == art_brief), None)
        if art_brief and art is None:
            raise ResourceNotFoundError('No saved art brief with that id')
        record = {'id': 'shotplan_' + uuid.uuid4().hex[:16], 'scene': scene, 'title': title.strip(),
                  'intention': intention.strip(), 'shots': shots, 'based_on': based_on,
                  'art_brief': art_brief, 'art_brief_digest': content_digest(art) if art else None,
                  'planning_digest': expected_planning_digest, 'script': canonical['script'],
                  'actor': actor.public_dict(), 'created_at': now()}
        return _append(root, state, 'direction_plans', record, actor)


def _review_fields(verdict, summary, findings, limitations):
    _text(summary, 'continuity summary', 4000)
    if verdict not in VERDICTS or not isinstance(findings, list) or len(findings) > 30:
        raise ValidationError('Invalid continuity verdict or findings')
    if not isinstance(limitations, list) or len(limitations) > 12:
        raise ValidationError('Continuity limitations must be a bounded list')
    for item in limitations:
        _text(item, 'limitation', 1000)
    for item in findings:
        if not isinstance(item, dict) or item.get('basis') not in BASES or item.get('severity') not in ('error', 'warning', 'advice'):
            raise ValidationError('Every continuity finding needs a basis and severity')
        for key in ('evidence', 'correction'):
            _text(item.get(key), key, 3000)
        if not isinstance(item.get('sources'), list) or any(not isinstance(source, str) for source in item['sources']):
            raise ValidationError('Findings need registered source IDs, not arbitrary paths or URLs')
    if verdict == 'ready_for_human' and any(item['severity'] != 'advice' or item['basis'] == 'unknown' for item in findings):
        raise ValidationError('Unresolved continuity concerns cannot be ready for human review')


def save_continuity_review(root: Path, *, plan, verdict, summary, findings, limitations,
                           expected_revision, expected_planning_digest, actor: Actor, scene=''):
    _review_fields(verdict, summary, findings, limitations); root = Path(root).resolve()
    if len(limitations) > 11:
        raise ValidationError('Keep one limitation slot for the actual inspection boundary')
    with scene_lock(root):
        state, context = _checked(root, expected_revision, expected_planning_digest)
        proposal = next((item for item in state.get('direction_plans', []) if item['id'] == plan), None)
        if plan and proposal is None:
            raise ResourceNotFoundError('No saved direction plan with that id')
        if scene:
            _scene(context, scene)
        if proposal and scene and proposal['scene'] != scene:
            raise ValidationError('Review scene must match the addressed proposal')
        if proposal and proposal['planning_digest'] != context['planning_digest']:
            raise ValidationError('Proposal sources changed; revise the plan before reviewing it')
        sources = context['evidence'] | ({'plan:' + plan: {'basis': 'authored', 'description': 'Proposed facts, not canonical or measured facts.'}} if proposal else {})
        for finding in findings:
            if any(source not in sources for source in finding['sources']):
                raise ValidationError('Continuity finding cites an unknown source')
            if finding['basis'] in ('authored', 'computed') and not any(
                    sources[source]['basis'] == finding['basis'] for source in finding['sources']):
                raise ValidationError('Claimed evidence basis needs a matching registered source')
        scope = proposal['scene'] if proposal else scene
        canonical_checks = [item['finding'] for item in context['evidence'].values() if 'finding' in item
                            and (not scope or item['finding'].get('scene_id') == scope)]
        checks = plan_checks(proposal, context) if proposal else canonical_checks
        if verdict == 'ready_for_human' and any(item['severity'] in ('warning', 'error') for item in checks):
            raise ValidationError('Computed proposal checks still need correction; the model cannot erase them')
        record = {'id': 'continuity_' + uuid.uuid4().hex[:16], 'plan': plan or '', 'scene': scope,
                  'plan_digest': content_digest(proposal) if proposal else None, 'planning_digest': expected_planning_digest,
                  'verdict': verdict, 'summary': summary.strip(), 'findings': findings, 'checks': checks,
                  'canonical_checks': canonical_checks,
                  'limitations': [*limitations, 'Text/canonical-record review; no pixel inspection.'],
                  'actor': actor.public_dict(), 'created_at': now()}
        return _append(root, state, 'continuity_reviews', record, actor)


def validate_direction_records(state):
    plans = state.get('direction_plans', []); reviews = state.get('continuity_reviews', [])
    if not isinstance(plans, list) or not isinstance(reviews, list):
        raise ValueError('Invalid directing journal lists')
    known = set()
    for plan in plans:
        if not isinstance(plan, dict) or not isinstance(plan.get('id'), str) or plan['id'] in known:
            raise ValueError('Invalid direction proposal identity')
        _plan_fields(plan.get('title'), plan.get('intention'), plan.get('shots'))
        if not isinstance(plan.get('planning_digest'), str) or not isinstance(plan.get('scene'), str):
            raise ValueError('Missing direction proposal sources')
        if plan.get('based_on') and not any(previous['id'] == plan['based_on'] and previous['scene'] == plan['scene']
                                            for previous in plans if previous['id'] in known):
            raise ValueError('Invalid retained proposal lineage')
        known.add(plan['id'])
    seen = set()
    for review in reviews:
        if (not isinstance(review, dict) or not isinstance(review.get('id'), str)
                or (review.get('plan') and review['plan'] not in known) or review.get('id') in seen
                or not isinstance(review.get('scene'), str) or not isinstance(review.get('planning_digest'), str)):
            raise ValueError('Invalid retained continuity review')
        _review_fields(review.get('verdict'), review.get('summary'), review.get('findings'), review.get('limitations'))
        seen.add(review['id'])


def directing_view(root, state=None, scene=''):
    state = load_creation(root) if state is None else state
    if not state.get('direction_plans') and not state.get('continuity_reviews'):
        return {'planning_digest': None, 'plans': [], 'reviews': []}
    context = planning_context(root)
    digest = context['planning_digest']
    plans = [{**item, 'stale': item['planning_digest'] != digest,
              'checks': plan_checks(item, context) if item['planning_digest'] == digest else [],
              'canonical': False} for item in state.get('direction_plans', []) if not scene or item['scene'] == scene]
    reviews = []
    for item in state.get('continuity_reviews', []):
        if scene and item['scene'] not in (scene, ''):
            continue
        superseded = any(plan.get('based_on') == item['plan'] for plan in state.get('direction_plans', []))
        proposal = next((plan for plan in state.get('direction_plans', []) if plan['id'] == item['plan']), None)
        changed_plan = bool(item['plan'] and (proposal is None or item.get('plan_digest') != content_digest(proposal)))
        reviews.append({**item, 'stale': item['planning_digest'] != digest or superseded or changed_plan, 'human_approval': False})
    return {'planning_digest': digest, 'plans': plans, 'reviews': reviews}


def current_direction_review(root, state, plan_id, review_id):
    view = directing_view(root, state)
    candidates = [item for item in view['reviews'] if item['plan'] == plan_id]
    return bool(candidates and candidates[-1]['id'] == review_id and not candidates[-1]['stale']
                and candidates[-1]['verdict'] == 'ready_for_human')
