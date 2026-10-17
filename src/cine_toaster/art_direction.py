"""Versioned visual briefs and advisory image reviews; never human approvals."""
from __future__ import annotations

import base64
import io
import uuid
from pathlib import Path

from .creation import _commit, content_digest, load_creation, reference_snapshot
from .creation_review import _text, inception_source_digest
from .errors import PermissionDeniedError, ResourceNotFoundError, RevisionConflictError, ValidationError
from .events import Event, append_event
from .state import Actor, now, scene_lock

VERDICTS = ('ready_for_human', 'needs_changes', 'inconclusive')


def validate_art_records(state):
    """Validate retained records on journal reads, including older journals."""
    known = set()
    for brief in state.get('art_briefs', []):
        if (not isinstance(brief, dict) or not isinstance(brief.get('id'), str) or brief['id'] in known
                or not isinstance(brief.get('inputs'), list) or not isinstance(brief.get('source_digest'), str)):
            raise ValueError('Invalid art brief')
        _brief_fields(brief.get('title'), brief.get('text'), brief.get('criteria'))
        if brief.get('based_on') and brief['based_on'] not in known:
            raise ValueError('Art brief lineage is missing')
        known.add(brief['id'])
    reviews = set()
    for review in state.get('visual_reviews', []):
        if (review.get('brief') not in known or review.get('id') in reviews
                or not isinstance(review.get('images'), list) or not review['images']):
            raise ValueError('Invalid visual review')
        brief = next(item for item in state['art_briefs'] if item['id'] == review['brief'])
        _review_fields(brief, review.get('verdict'), review.get('findings'), review.get('summary'))
        reviews.add(review['id'])


def _brief_fields(title, text, criteria):
    _text(title, 'title', 240); _text(text, 'visual brief', 12000)
    if not isinstance(criteria, list) or not 1 <= len(criteria) <= 12:
        raise ValidationError('Specify 1 to 12 checkable visual criteria')
    for criterion in criteria:
        _text(criterion, 'criterion', 1000)
    if len(set(criteria)) != len(criteria):
        raise ValidationError('Visual criteria must be distinct')


def _review_fields(brief, verdict, findings, summary):
    _text(summary, 'review summary')
    if verdict not in VERDICTS or not isinstance(findings, list) or len(findings) != len(brief['criteria']):
        raise ValidationError('Review every brief criterion exactly once')
    if any(not isinstance(item, dict) for item in findings):
        raise ValidationError('Every finding must be a structured criterion observation')
    if sorted(item.get('criterion', '') for item in findings) != sorted(brief['criteria']):
        raise ValidationError('Review criteria must match the exact brief')
    for item in findings:
        if item.get('status') not in ('pass', 'fail', 'uncertain'):
            raise ValidationError('Finding status must be pass, fail or uncertain')
        _text(item.get('evidence'), 'visible evidence')
        _text(item.get('correction'), 'correction or reason no correction is needed')
    if verdict == 'ready_for_human' and any(item['status'] != 'pass' for item in findings):
        raise ValidationError('Failed or uncertain criteria cannot be ready for human review')
    if verdict == 'needs_changes' and not any(item['status'] == 'fail' for item in findings):
        raise ValidationError('Needs changes requires at least one failed criterion')


def _checked(root, expected_revision, expected_source_digest):
    state = load_creation(root)
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValidationError('expected_revision must be a non-negative integer')
    if expected_revision != state['revision']:
        raise RevisionConflictError(expected_revision, state['revision'])
    if not expected_source_digest or expected_source_digest != inception_source_digest(root, state):
        raise ValidationError('Creative material changed; reread before publishing')
    return state


def _append(root, state, key, record, actor):
    if actor.kind != 'agent':
        raise PermissionDeniedError('Art briefs and prevalidation are agent work, not human gate decisions')
    changed = {**state, 'revision': state['revision'] + 1, key: [*state.get(key, []), record]}
    _commit(root, changed)
    append_event(root, Event.create('creation.' + key, state['project_id'], record_id=record['id'],
                                   revision=changed['revision'], actor=actor.public_dict()))
    return {'revision': changed['revision'], 'record': record}


def save_art_brief(root: Path, *, title, text, criteria, references, expected_revision,
                   expected_source_digest, actor: Actor, concept='', based_on=''):
    _brief_fields(title, text, criteria)
    root = Path(root).resolve()
    with scene_lock(root):
        state = _checked(root, expected_revision, expected_source_digest)
        inputs = reference_snapshot(root, references)
        if concept:
            source = next((item for item in state['drafts'] if item['id'] == concept and item['kind'] == 'concept'), None)
            if not source:
                raise ResourceNotFoundError('No saved concept with that id')
            inputs.insert(0, {'kind': 'concept', 'id': concept, 'sha256': content_digest(source)})
        if based_on and not any(item['id'] == based_on for item in state.get('art_briefs', [])):
            raise ResourceNotFoundError('No previous art brief with that id')
        record = {'id': 'art_' + uuid.uuid4().hex[:16], 'title': title.strip(), 'text': text.strip(),
                  'criteria': criteria, 'inputs': inputs, 'concept': concept, 'based_on': based_on,
                  'source_digest': expected_source_digest, 'actor': actor.public_dict(), 'created_at': now()}
        return _append(root, state, 'art_briefs', record, actor)


def image_package(root: Path, references: list[str]):
    """Only registered, digest-checked raster files; no model-supplied paths/URLs."""
    from PIL import Image

    if not isinstance(references, list) or not 1 <= len(references) <= 4:
        raise ValidationError('Inspect 1 to 4 reference records per review')
    root = Path(root).resolve()
    snapshots = reference_snapshot(root, references)
    images, total = [], 0
    for snapshot in snapshots:
        for name, sha256 in snapshot['files'].items():
            path = root / 'references' / snapshot['id'] / name
            if path.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp'):
                continue
            if path.stat().st_size > 8 * 1024 * 1024:
                raise ValidationError('Review images must be at most 8 MiB each')
            data = path.read_bytes()
            import hashlib
            if hashlib.sha256(data).hexdigest() != sha256:
                raise ValidationError('Image changed while being inspected')
            try:
                with Image.open(io.BytesIO(data)) as image:
                    if image.width * image.height > 20_000_000 or getattr(image, 'n_frames', 1) != 1:
                        raise ValidationError('Use a still raster of at most 20 megapixels')
                    mime = {'PNG': 'image/png', 'JPEG': 'image/jpeg', 'WEBP': 'image/webp'}.get(image.format)
                    image.verify()
                if not mime:
                    raise ValueError('unsupported format')
            except (OSError, ValueError) as error:
                raise ValidationError('Reference contains an unreadable or unsupported raster') from error
            total += len(data)
            images.append({'reference': snapshot['id'], 'file': name, 'sha256': sha256,
                           'mime_type': mime, 'data': base64.b64encode(data).decode('ascii')})
            if total > 24 * 1024 * 1024 or len(images) > 8:
                raise ValidationError('Inspect at most 8 images / 24 MiB per review')
    if not images or any(not any(image['reference'] == ref for image in images) for ref in references):
        raise ValidationError('Every selected reference must contain a supported still image')
    evidence = [{key: value for key, value in image.items() if key != 'data'} for image in images]
    return {'images': images, 'images_digest': content_digest(evidence), 'references': snapshots}


def save_visual_review(root: Path, *, brief, references, images_digest, verdict, findings, summary,
                       expected_revision, expected_source_digest, actor: Actor, targets=None):
    root = Path(root).resolve()
    with scene_lock(root):
        state = _checked(root, expected_revision, expected_source_digest)
        source = next((item for item in state.get('art_briefs', []) if item['id'] == brief), None)
        if source is None:
            raise ResourceNotFoundError('No saved art brief with that id')
        _review_fields(source, verdict, findings, summary)
        package = image_package(root, references)
        targets = references if targets is None else targets
        if (not isinstance(targets, list) or not targets or any(not isinstance(item, str) for item in targets)
                or len(set(targets)) != len(targets) or any(item not in references for item in targets)):
            raise ValidationError('Review targets must name distinct inspected reference records')
        if package['images_digest'] != images_digest:
            raise ValidationError('Inspected images changed; perform visual review again')
        record = {'id': 'visual_' + uuid.uuid4().hex[:16], 'brief': brief,
                  'brief_digest': content_digest(source), 'references': package['references'],
                  'targets': targets,
                  'images': [{key: value for key, value in image.items() if key != 'data'} for image in package['images']],
                  'images_digest': images_digest, 'verdict': verdict, 'findings': findings, 'summary': summary,
                  'source_digest': expected_source_digest, 'actor': actor.public_dict(), 'created_at': now()}
        return _append(root, state, 'visual_reviews', record, actor)


def art_view(root: Path, state: dict, source_digest):
    reviews = []
    for review in state.get('visual_reviews', []):
        changed = review['source_digest'] != source_digest
        try:
            changed |= reference_snapshot(root, [item['id'] for item in review['references']]) != review['references']
        except (ValidationError, ResourceNotFoundError, OSError):
            changed = True
        # A newer revision of the same brief lineage also invalidates its previous review.
        changed |= any(item.get('based_on') == review['brief'] for item in state.get('art_briefs', []))
        reviews.append({**review, 'stale': changed, 'human_approval': False})
    return {'briefs': state.get('art_briefs', []), 'reviews': reviews}
