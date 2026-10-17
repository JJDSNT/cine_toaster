"""Read-only filmmaking work structure, derived from the addressed production.

This is product context, not repository development memory or a second manifest.
It describes scope and responsibilities; it never establishes readiness/approval.
"""
from __future__ import annotations

from typing import Any

from .errors import ResourceNotFoundError, ValidationError


WORK_POLICY = """Work/review unit: the canonical sequence, in its declared scene order.
Scenes and shots are internal subtasks or explicitly partial studies, not sequence
deliveries. A focused scene/page does not narrow the director's review unit.
Use actual sequence membership, including intermediate scene subdivisions; never
infer a numeric range, invent a sequence or assume one film's grouping fits another.
Flow: Inception -> screenplay <-> storyboard -> blockouts/3D storyboard -> master
images -> clips -> assembled sequences. Revisit stages when needed; existing films
need not restart at Inception. Stage presence is not readiness or human approval.
Before requesting sequence transition review, compare exact original Inception
intention/reference versions with screenplay beats and the ordered storyboard;
use independent narrative/continuity and actual image review, not just an artist's
brief. Missing drawings, mapping, inspection or agent-fixable gaps are agent-owned
work, not an empty approval request. Label every partial study's actual scope.
Use shared application commands and retained decisions. Preserve versions/images.
Only humans decide creative gates; approval never implies generation quota consent.
The GUI situates the human with evidence, agent work and concrete decisions; do not
delegate authoring forms or resolvable work to them. Report missing capabilities
honestly: knowing this flow does not implement its unfinished transitions/reviews.
"""


def work_structure(production: dict[str, Any], *, scene: str = "", sequence: str = "") -> dict[str, Any]:
    """Canonical membership is explicit, ordered and never replaced by UI focus.

    Unknown declarations are retained as missing, not silently dropped. A missing
    grouping is a gap; it is not permission to invent one from scene numbering.
    """
    scenes = {item['id']: item for item in production.get('scenes') or []}
    if scene and scene not in scenes:
        raise ResourceNotFoundError(f"No canonical scene {scene!r}")
    sequences = production.get('sequences') or []
    if sequence and not any(item['id'] == sequence for item in sequences):
        raise ResourceNotFoundError(f"No canonical sequence {sequence!r}")
    selected = next((item for item in sequences if item['id'] == sequence), None)
    if selected is not None and scene and scene not in selected.get('scene_ids', []):
        raise ValidationError('The focused scene is outside the addressed sequence')
    placed = {identity for item in sequences for identity in item.get('scene_ids') or []}
    return {
        'project_id': production.get('id'),
        'review_unit': 'sequence',
        'policy': WORK_POLICY,
        'focused_scene': scene,
        'addressed_sequence': sequence,
        'scene_sequences': [item['id'] for item in sequences if scene and scene in (item.get('scene_ids') or [])],
        'sequences': [{
            'id': item['id'], 'label': item.get('label') or item['id'], 'act': item.get('act') or '',
            'scene_ids': list(item.get('scene_ids') or []),
            'missing_scene_ids': [identity for identity in item.get('scene_ids') or [] if identity not in scenes],
            'shot_count': sum(len(scenes[identity].get('shots') or [])
                              for identity in item.get('scene_ids') or [] if identity in scenes),
        } for item in sequences if not sequence or item['id'] == sequence],
        'unassigned_scene_ids': [identity for identity in scenes if identity not in placed],
        'authority': 'Canonical production manifest; focus is navigation, not approval or permission.',
    }
