"""Explicit sequence-review intent, not another job queue or a human gate."""
from __future__ import annotations

import re
import uuid
from pathlib import Path
from urllib.parse import urlencode

from .creation import _commit, content_digest, load_creation
from .errors import PermissionDeniedError, ResourceNotFoundError, RevisionConflictError, ValidationError
from .events import Event, append_event
from .production_context import work_structure
from .project import load_production
from .state import Actor, now, scene_lock

KIND = 'inception_storyboard_sequence_review'
OWNER = 'coordinator'
INSTRUCTION = ('Prepare an independent sequence-wide comparison of original Inception intention/reference versions, '
               'screenplay beats and ordered storyboard drawings. Resolve agent-owned gaps; report missing '
               'capabilities honestly. Do not substitute a local scene study or ask for sequence approval before '
               'a complete current review exists. Preserve versions; generation needs separate quota consent.')


def validate_sequence_work(state):
    requests = state.get('sequence_review_requests', [])
    if not isinstance(requests, list):
        raise ValueError('Invalid sequence review request list')
    known = {}
    for item in requests:
        if (not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id']
                or item['id'] in known or item.get('kind') != KIND or item.get('owner') != OWNER
                or item.get('state') != 'pending_agent' or item.get('dispatch_status') != 'not_dispatched'
                or any(not isinstance(item.get(key), str) or not item[key].strip()
                       for key in ('sequence', 'title', 'rationale', 'created_at'))
                or len(item['title']) > 240 or len(item['rationale']) > 4000
                or not isinstance(item.get('scene_ids'), list) or not item['scene_ids']
                or any(not isinstance(identity, str) or not identity for identity in item['scene_ids'])
                or len(set(item['scene_ids'])) != len(item['scene_ids'])
                or not isinstance(item.get('source_digest'), str)
                or not re.fullmatch('[0-9a-f]{64}', item['source_digest'])
                or not isinstance(item.get('actor'), dict) or item['actor'].get('kind') not in ('human', 'agent')
                or not isinstance(item['actor'].get('id'), str) or not item['actor']['id']
                or not isinstance(item.get('based_on'), str)):
            raise ValueError('Invalid retained sequence review request')
        previous = known.get(item['based_on']) if item['based_on'] else None
        if item['based_on'] and (not previous or previous['sequence'] != item['sequence']):
            raise ValueError('Invalid sequence review request lineage')
        known[item['id']] = item


def _source(production, material_digest):
    if material_digest is None:
        return None
    return content_digest({'material': material_digest,
                           'sequences': [{'id': item['id'], 'scene_ids': item.get('scene_ids') or []}
                                         for item in production.get('sequences') or []]})


def sequence_work_view(root, state=None, production=None, *, material_digest=None):
    """Current explicit requests only; never invent work for every missing shot."""
    from .creation_review import inception_source_digest
    from .storyboard import load_storyboard

    root = Path(root).expanduser().resolve()
    production = load_production(root) if production is None else production
    state = load_creation(root, production=production) if state is None else state
    if material_digest is None:
        try:
            material_digest = inception_source_digest(root, state)
        except (ValidationError, ResourceNotFoundError, OSError):
            material_digest = None
    source = _source(production, material_digest)
    latest = {item['sequence']: item for item in state.get('sequence_review_requests', [])}
    items = []
    boards = load_storyboard(root, production=production)['candidates'] if latest else []
    recorded = {(item['scene'], item['shot']) for item in boards}
    scenes = {item['id']: item for item in production['scenes']}
    sequences = {item['id']: item for item in production.get('sequences') or []}
    for sequence_id, request in latest.items():
        sequence = sequences.get(sequence_id)
        members = list(sequence.get('scene_ids') or []) if sequence else []
        shots = [(identity, shot['id']) for identity in members if identity in scenes
                 for shot in scenes[identity].get('shots') or []]
        missing = [{'scene': scene, 'shot': shot} for scene, shot in shots if (scene, shot) not in recorded]
        gaps = []
        if not sequence or any(identity not in scenes for identity in members):
            gaps.append({'code': 'scope_unavailable', 'owner': OWNER,
                         'description': 'The requested canonical sequence or some member scenes are unavailable.',
                         'next_action': 'Resolve the canonical scope; do not silently narrow this request.'})
        if source != request['source_digest']:
            gaps.append({'code': 'sources_changed', 'owner': OWNER,
                         'description': 'Source evidence or canonical sequence order changed since this request.',
                         'next_action': 'Reread current inputs and retain a refreshed request before reviewing.'})
        if missing or not shots:
            gaps.append({'code': 'storyboard_incomplete', 'owner': 'art_direction',
                         'description': f'{len(missing)} of {len(shots)} canonical shots have no retained drawing record.'
                                        if shots else 'The sequence has no canonical shots to compare.',
                         'next_action': 'Develop missing ordered evidence through existing tools; do not infer generation consent.'})
        gaps.append({'code': 'sequence_review_capability_missing', 'owner': OWNER,
                     'description': 'The complete source-to-beat comparison package and independent sequence adherence validator are not implemented.',
                     'next_action': 'Report this capability blocker. Existing local art/continuity reviews do not complete this task.'})
        items.append({**request, 'sequence_label': (sequence or {}).get('label') or sequence_id,
                      'current_scene_ids': members, 'scope_changed': members != request['scene_ids'],
                      'sources_changed': source != request['source_digest'],
                      'instruction': INSTRUCTION, 'next_action': gaps[0]['next_action'], 'gaps': gaps,
                      'review_roles': ['inception', 'directing', 'continuity', 'visual_prevalidation'],
                      'coverage': {'shots': len(shots), 'shots_with_records': len(shots) - len(missing),
                                   'missing_shots': missing, 'meaning': 'Record presence only, not image inspection or approval.'},
                      'human_action_required': False, 'execution_supported': False,
                      'url': '/app/decisions.html?' + urlencode({'work': request['id']}) + '#agent-work'})
    return {'project_id': production['id'], 'revision': state['revision'], 'source_digest': source,
            'pending_count': len(items), 'items': items,
            'sequences': [{'id': item['id'], 'label': item.get('label') or item['id'],
                           'scene_ids': item.get('scene_ids') or []} for item in sequences.values()],
            'execution': 'Requests are retained intent. No background dispatcher or completed review is implied.'}


def request_sequence_review(root, *, sequence, title, rationale, expected_revision, expected_source_digest, actor):
    """Append authorised work through the shared journal command; never approve."""
    if actor.kind not in ('human', 'agent'):
        raise PermissionDeniedError('Only human or agent actors can request production review work')
    if not isinstance(sequence, str) or not sequence.strip():
        raise ValidationError('sequence must be a canonical sequence id')
    for value, label, limit in ((title, 'title', 240), (rationale, 'rationale', 4000)):
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValidationError(f'{label} must be non-empty text of at most {limit} characters')
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValidationError('expected_revision must be a non-negative integer')
    root = Path(root).expanduser().resolve()
    with scene_lock(root):
        production = load_production(root)
        state = load_creation(root, production=production)
        if state['revision'] != expected_revision:
            raise RevisionConflictError(expected_revision, state['revision'])
        scope = work_structure(production, sequence=sequence)['sequences'][0]
        if not scope['scene_ids'] or scope['missing_scene_ids']:
            raise ValidationError('Review work requires a non-empty canonical sequence with existing member scenes')
        view = sequence_work_view(root, state, production)
        if not view['source_digest'] or view['source_digest'] != expected_source_digest:
            raise ValidationError('Production sources or sequence scope changed; reread before requesting work')
        previous = next((item for item in view['items'] if item['sequence'] == sequence), None)
        if previous and previous['source_digest'] == view['source_digest']:
            return {'revision': state['revision'], 'request': next(item for item in state['sequence_review_requests']
                     if item['id'] == previous['id']), 'unchanged': True}
        item = {'id': 'seqwork_' + uuid.uuid4().hex[:16], 'kind': KIND, 'owner': OWNER,
                'state': 'pending_agent', 'dispatch_status': 'not_dispatched', 'sequence': sequence,
                'scene_ids': scope['scene_ids'], 'title': title.strip(), 'rationale': rationale.strip(),
                'source_digest': view['source_digest'], 'based_on': previous['id'] if previous else '',
                'actor': actor.public_dict(), 'created_at': now()}
        committed = {**state, 'revision': state['revision'] + 1,
                     'sequence_review_requests': [*state.get('sequence_review_requests', []), item]}
        validate_sequence_work(committed)
        _commit(root, committed)
        append_event(root, Event.create('creation.sequence_review_requested', state['project_id'],
                     request_id=item['id'], sequence=sequence, revision=committed['revision'], actor=actor.public_dict()))
        return {'revision': committed['revision'], 'request': item, 'unchanged': False}
