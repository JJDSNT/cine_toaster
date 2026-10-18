"""Approved source snapshots consumed by existing stage commands, not a queue."""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from urllib.parse import urlencode

from .creation import content_digest, load_creation, reference_snapshot
from .errors import PermissionDeniedError, ResourceNotFoundError, RevisionConflictError, ValidationError
from .project import load_production
from .references import digest
from .state import Actor, now, scene_lock
from .storyboard import load_storyboard, register_storyboard_candidate


def target_members(target):
    """Every (scene, shot) a handoff target covers, in order: one scene, or a canonical sequence."""
    if 'sequence' in target:
        return [(item['scene'], shot) for item in target['scenes'] for shot in item['shots']]
    return [(target['scene'], shot) for shot in target['shots']]


def target_scenes(target):
    return [item['scene'] for item in target['scenes']] if 'sequence' in target else [target['scene']]


def sequence_target(production, sequence):
    """The canonical sequence as a handoff target: its declared scenes in order, each with all its shots.

    Membership comes from the production's `sequences` (ADR 0008), never from scene numbering:
    Singular's Genebra is 1-01..1-04 with 1-02A/B/C because the film says so.
    """
    from .production_context import work_structure
    try:
        scope = work_structure(production, sequence=sequence)['sequences']
    except (ResourceNotFoundError, ValidationError):
        return None
    chosen = next((item for item in scope if item['id'] == sequence), None)
    if not chosen or not chosen['scene_ids'] or chosen['missing_scene_ids']:
        return None
    scenes = {item['id']: item for item in production['scenes']}
    members = [{'scene': identity, 'shots': [shot['id'] for shot in scenes[identity]['shots']]}
               for identity in chosen['scene_ids']]
    if not all(item['shots'] for item in members):
        return None
    return {'sequence': sequence, 'label': chosen['label'], 'scenes': members}


def preview_handoff(root, assessment, state=None):
    state = load_creation(root) if state is None else state
    proposal = assessment['proposal']; production = load_production(root)
    plan = next((item for item in state.get('direction_plans', []) if item['id'] == proposal.get('direction_plan')), None)
    target = proposal.get('target')
    if target is None and isinstance(proposal.get('sequence'), str) and proposal['sequence']:
        # The director's unit of review: a whole canonical sequence (ADR 0035).
        target = sequence_target(production, proposal['sequence'])
    if target is None and plan:
        associated = [item.get('existing_shot') for item in plan['shots']]
        target = {'scene': plan['scene'], 'shots': associated} if all(associated) else None
    if target is None and not plan:
        # A legacy suggestion is shown to the human, not treated as authority.
        scope = proposal['scope']
        mentioned = [scene for scene in production['scenes'] if re.search(r'(?<![\w-])' + re.escape(scene['id']) + r'(?![\w-])', scope)]
        if len(mentioned) == 1:
            scene = mentioned[0]
            shots = [shot['id'] for shot in scene['shots'] if re.search(r'(?<![\w-])' + re.escape(shot['id']) + r'(?![\w-])', scope)]
            if shots:
                target = {'scene': scene['id'], 'shots': shots}
    if isinstance(target, dict) and 'sequence' in target:
        if target != sequence_target(production, target['sequence']):
            target = None  # a stale or hand-made sequence target is never authority
    elif target is not None:
        scene = next((item for item in production['scenes'] if item['id'] == target.get('scene')), None) if isinstance(target, dict) else None
        shots = target.get('shots') if isinstance(target, dict) else None
        if (not scene or not isinstance(shots, list) or not shots or any(not isinstance(s, str) for s in shots)
                or len(set(shots)) != len(shots) or any(s not in {x['id'] for x in scene['shots']} for s in shots)):
            target = None
    value = {'destination': proposal['destination'], 'target': target,
             'can_advance': proposal['destination'] == 'storyboard' and target is not None and proposal.get('review_kind') != 'storyboard_candidates',
             'scope': proposal['scope'], 'assessment': assessment['id']}
    return {**value, 'sha256': content_digest(value)}


def _snapshot(root, state, pinned=None):
    from .directing import _projection
    production = load_production(root)
    public = json.loads(json.dumps(_projection(production), default=str))
    scripts = []
    for name in production.get('script_files', []):
        path = (root / name).resolve()
        if not path.is_relative_to(root):
            raise ValidationError('Screenplay input escapes this project')
        scripts.append({'path': name, 'sha256': digest(path)})
    refs = [item['id'] for item in pinned['references']] if pinned else [item['id'] for item in state.get('_assessment_references', [])]
    result = {'production': content_digest(public), 'scripts': scripts, 'references': reference_snapshot(root, refs)}
    for key in ('drafts', 'rounds', 'art_briefs', 'direction_plans', 'continuity_reviews'):
        items = state.get(key, [])
        if pinned:
            ids = {item['id'] for item in pinned[key]}
            items = [item for item in items if item['id'] in ids]
        result[key] = [{'id': item['id'], 'sha256': content_digest(item)} for item in items]
    boards = load_storyboard(root)['candidates']
    if pinned:
        ids = {item['id'] for item in pinned['storyboard']}
        boards = [item for item in boards if item['id'] in ids]
    result['storyboard'] = []
    for item in boards:
        path = (root / item['image']['path']).resolve()
        if not path.is_relative_to(root):
            raise ValidationError('Storyboard input escapes this project')
        result['storyboard'].append({'id': item['id'], 'sha256': content_digest(item), 'image': digest(path)})
    return result


def make_handoff(root, state, assessment, decision, expected_preview):
    preview = preview_handoff(root, assessment, state)
    if not preview['can_advance'] or preview['sha256'] != expected_preview:
        raise ValidationError('The explicit scene/shot or sequence handoff changed or is unavailable; inspect the scoped proposal')
    snapshot = _snapshot(root, {**state, '_assessment_references': assessment['materials']['references']})
    return {'id': 'handoff_' + uuid.uuid4().hex[:16], 'assessment': assessment['id'], 'decision': decision['id'],
            'destination': preview['destination'], 'target': preview['target'], 'scope': preview['scope'],
            'instruction': decision['next_agent_action']['instruction'], 'sources': snapshot,
            'sources_sha256': content_digest(snapshot), 'created_at': now(), 'actor': decision['actor']}


def validate_handoffs(state):
    records = state.get('stage_handoffs', [])
    if not isinstance(records, list):
        raise ValueError('Invalid handoff journal')
    ids, decisions = set(), set()
    for item in records:
        if (not isinstance(item, dict) or not isinstance(item.get('id'), str) or item['id'] in ids
                or item.get('decision') in decisions or not isinstance(item.get('sources'), dict)
                or content_digest(item['sources']) != item.get('sources_sha256')
                or not isinstance(item.get('target'), dict) or item.get('destination') != 'storyboard'):
            raise ValueError('Invalid retained stage handoff')
        target = item['target']
        if 'sequence' in target:
            parts = target.get('scenes')
            valid = (isinstance(target['sequence'], str) and isinstance(parts, list) and parts
                     and all(isinstance(part, dict) and isinstance(part.get('scene'), str)
                             and isinstance(part.get('shots'), list) and part['shots']
                             and all(isinstance(shot, str) for shot in part['shots'])
                             and len(set(part['shots'])) == len(part['shots']) for part in parts)
                     and len({part['scene'] for part in parts}) == len(parts))
        else:
            valid = (isinstance(target.get('scene'), str) and isinstance(target.get('shots'), list) and target['shots']
                     and all(isinstance(shot, str) for shot in target['shots'])
                     and len(set(target['shots'])) == len(target['shots']))
        if (not valid
                or any(not isinstance(item['sources'].get(key), list) for key in
                       ('scripts', 'references', 'drafts', 'rounds', 'art_briefs', 'direction_plans', 'continuity_reviews', 'storyboard'))):
            raise ValueError('Invalid retained handoff target/source snapshot')
        decision = next((d for d in state.get('assessment_decisions', []) if d.get('id') == item.get('decision')), None)
        if not decision or decision['outcome'] != 'approved' or decision['assessment'] != item.get('assessment'):
            raise ValueError('Handoff requires an exact approved human decision')
        ids.add(item['id']); decisions.add(item['decision'])


def handoff_current(root, state, item):
    try:
        # Additive consumer artifacts do not invalidate pinned source records.
        return content_digest(_snapshot(Path(root), state, item['sources'])) == item['sources_sha256']
    except (OSError, ValidationError, KeyError, IndexError):
        return False


def handoff_view(root, state=None):
    state = load_creation(root) if state is None else state
    boards = load_storyboard(root)['candidates'] if state.get('stage_handoffs') else []
    views = []
    latest = (state.get('assessments') or [{}])[-1].get('id')
    for item in state.get('stage_handoffs', []):
        outputs = [{'id': board['id'], 'scene': board['scene'], 'shot': board['shot'],
                    'url': '/app/preproduction.html?' + urlencode({'scene': board['scene'], 'shot': board['shot'], 'candidate': board['id']})}
                   for board in boards if board.get('provenance', {}).get('handoff') == item['id']]
        # A shot is drawn when it has any storyboard drawing: a newer request over the same sequence
        # inherits the drawings made under the earlier one (they are versions, never discarded).
        drawn = {(board['scene'], board['shot']) for board in boards}
        members = target_members(item['target'])
        views.append({**item, 'stale': not handoff_current(root, state, item), 'outputs': outputs,
                      # A newer request (a sequence after a scene study) supersedes it: it is history, not work.
                      'superseded': item['assessment'] != latest,
                      'missing': [{'scene': scene, 'shot': shot} for scene, shot in members if (scene, shot) not in drawn],
                      'coverage': {'shots': len(members), 'drawn': len(members) - len([1 for pair in members if pair not in drawn])},
                      'execution': 'not_tracked_here'})
    return views


def publish_storyboard_reference(root, *, handoff, scene, shot, reference, file, title,
                                 expected_revision, expected_storyboard_revision, actor: Actor,
                                 based_on='', note=''):
    if actor.kind != 'agent':
        raise PermissionDeniedError('Stage publication is agent work, not a human gate')
    if type(expected_revision) is not int or type(expected_storyboard_revision) is not int:
        raise ValidationError('Both expected revisions must be integers')
    root = Path(root).resolve()
    with scene_lock(root):
        state = load_creation(root)
        if state['revision'] != expected_revision:
            raise RevisionConflictError(expected_revision, state['revision'])
        item = next((item for item in state.get('stage_handoffs', []) if item['id'] == handoff), None)
        if not item:
            raise ResourceNotFoundError('No approved stage handoff with that id')
        if not handoff_current(root, state, item):
            raise ValidationError('Approved handoff inputs changed; reassess before publishing')
        if state.get('assessments', [])[-1]['id'] != item['assessment']:
            raise ValidationError('Another assessment superseded this development request')
        if (scene, shot) not in target_members(item['target']):
            raise PermissionDeniedError('Storyboard target exceeds the human-approved handoff')
        snapshot = reference_snapshot(root, [reference])[0]
        if not isinstance(file, str) or file not in snapshot['files']:
            raise ValidationError('Select an actual registered image file, not an arbitrary path')
        source = (root / 'references' / reference / file).resolve()
        if not source.is_relative_to(root):
            raise ValidationError('Reference image escapes this project')
        for board in load_storyboard(root)['candidates']:
            provenance = board.get('provenance', {})
            if (board['scene'] == scene and board['shot'] == shot and provenance.get('handoff') == handoff
                    and provenance.get('reference_sha256') == snapshot['sha256'] and provenance.get('reference_file') == file
                    and board['based_on'] == based_on):
                return {'revision': load_storyboard(root)['revision'], 'candidate': board, 'replayed': True}
        return register_storyboard_candidate(root, scene=scene, shot=shot, image=source, title=title,
            expected_revision=expected_storyboard_revision, actor=actor, references=[reference], based_on=based_on, note=note,
            provenance={'handoff': handoff, 'decision': item['decision'], 'reference': reference,
                        'reference_file': file, 'reference_sha256': snapshot['sha256'],
                        'use': 'Reused registered image; generation provenance remains in its reference record.'})
