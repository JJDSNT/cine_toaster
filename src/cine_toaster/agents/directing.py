"""Directing/shot planning and a separate canonical-continuity reviewer."""
from __future__ import annotations

import json
import uuid


from .inception import bounded
from .loop import Loop, step
from .reads import production_work
from .roles import ROLES
from ..production_context import WORK_POLICY, work_structure

MAX_STEPS, MAX_REVIEWS = (ROLES["directing"].budgets[key] for key in ("steps", "reviews"))
MAX_CONTEXT = 48000

DIRECTING_SYSTEM = """You are Directing / Shot Planning inside Cine Toaster's Agent Runtime.
The existing Production Coordinator delegated this task; you are not another
coordinator or Producer. Speak the director's language. Turn screenplay intention
and relevant saved art direction into filmable ordered shot proposals: action,
framing, camera intent, duration, coverage and entry/exit facts. Read the addressed
scene and whole-film continuity context; do not confuse a scene with the film.
Use save_plan to publish real retained work. Proposed IDs are local to the draft;
existing_shot optionally names a real shot. script_units are the exact indices
of the linked scene's screenplay, never invented or from another scene.
Camera descriptions and entry/exit facts are PROPOSALS, not measured geometry.
Use based_on for corrections, preserving versions and all existing images.
review_continuity sends the exact saved plan to a separate reviewer. Correct
agent-fixable coverage/state problems using the review; do not outsource forms
or fixable work to the person. request_review needs a current successful review
and supplies a concrete question/scope/why/next_step in the director's language.
Approval here is only of the proposal, not canonical shot promotion or storyboard
approval. You cannot write manifests, promote a screenplay/shot plan, generate
images, change declared continuity or decide gates. If approved direction asks
for an unsupported downstream mutation, disclose that actual gap; don't invent
completion or request the same approval again. Art development can be delegated
to the existing Art Direction role, not a new generation path.
read_context / read_scene explicitly refresh records after a conflict. Inspect
receipts before claiming success. No shell, arbitrary paths or web research.
"""

CONTINUITY_SYSTEM = """You are Script Supervisor / Continuity inside Cine Toaster.
Use the existing canonical continuity ledger and computed geometry/coverage
findings. Never create another ledger, silently change facts, override a human
exception, approve a gate or claim pixel inspection from text/metadata.
Distinguish authored declarations, computed checks, inference and unknowns.
When asked to inspect continuity, use review_continuity to retain an actual
evidence-based report; plan may be empty for a canonical scene/film audit.
Request a narrower scene only when the actual context cannot fit. Use the
director's language. You can read_context, read_scene, review_continuity and
respond. Do not invent a job, completed render, finding source or global pass.
"""

REVIEW_SYSTEM = """You are the independent Script Supervisor / Continuity reviewer.
This is a fresh review call: compare the exact supplied shot proposal (if any)
against canonical screenplay units, the EXISTING continuity ledger, neighbour
context and computed findings. Proposed states are not production facts. Check
coverage, joins, identity/age/wardrobe/props when declared, screen direction and
narrative progression. Respect authored changes and human exceptions. Never
infer a continuity break merely from an intentional time/age jump.
Findings need basis authored/computed/inferred/unknown, severity error/warning/
advice, concrete evidence, correction and registered source IDs. Authored and
computed claims must cite a matching source basis. Proposed facts use plan:<id>
and must be described as proposed, not canonical. Missing evidence is uncertainty,
not a pass. Do not pretend to inspect images or to numerically test a proposed
camera described only in prose. Computed proposal checks cannot be erased by
your opinion. Verdict is advisory ready_for_human / needs_changes / inconclusive,
never human approval or a film-wide quality certificate. Write in the director's
language and disclose the actual scope/limitations.
"""

TEXT = {'type': 'string'}
FACT = {'type': 'object', 'properties': {'subject': TEXT, 'attribute': TEXT, 'value': TEXT},
        'required': ['subject', 'attribute', 'value']}
SHOT = {'type': 'object', 'properties': {
    **{key: TEXT for key in ('id', 'label', 'action', 'framing', 'camera_intent', 'existing_shot', 'transition_intent')},
    'duration_seconds': {'type': 'number'}, 'script_units': {'type': 'array', 'items': {'type': 'integer'}},
    'state_in': {'type': 'array', 'items': FACT}, 'state_out': {'type': 'array', 'items': FACT}},
    'required': ['id', 'label', 'action', 'framing', 'camera_intent', 'duration_seconds', 'script_units', 'state_in', 'state_out']}
SCHEMA = {'type': 'object', 'properties': {
    'action': {'type': 'string', 'enum': ['save_plan', 'review_continuity', 'read_context', 'read_scene',
              'request_review', 'delegate_art_direction', 'respond']},
    'reply': TEXT, 'status': {'type': 'string', 'enum': ['complete', 'needs_direction', 'needs_review', 'blocked']},
    'scene': TEXT, 'plan': TEXT,
    'draft': {'type': 'object', 'properties': {'scene': TEXT, 'title': TEXT, 'intention': TEXT,
              'shots': {'type': 'array', 'items': SHOT}, 'based_on': TEXT, 'art_brief': TEXT},
              'required': ['scene', 'title', 'intention', 'shots']},
    'review_request': {'type': 'object', 'properties': {key: TEXT for key in ('question', 'scope', 'why', 'next_step')},
                       'required': ['question', 'scope', 'why', 'next_step']},
}, 'required': ['action', 'reply']}
REVIEW_SCHEMA = {'type': 'object', 'properties': {
    'verdict': {'type': 'string', 'enum': ['ready_for_human', 'needs_changes', 'inconclusive']},
    'summary': TEXT, 'limitations': {'type': 'array', 'items': TEXT},
    'findings': {'type': 'array', 'items': {'type': 'object', 'properties': {
        'basis': {'type': 'string', 'enum': ['authored', 'computed', 'inferred', 'unknown']},
        'severity': {'type': 'string', 'enum': ['error', 'warning', 'advice']},
        'evidence': TEXT, 'correction': TEXT, 'sources': {'type': 'array', 'items': TEXT}},
        'required': ['basis', 'severity', 'evidence', 'correction', 'sources']}}},
    'required': ['verdict', 'summary', 'findings', 'limitations']}


DIRECTING_SYSTEM += '\n' + WORK_POLICY
CONTINUITY_SYSTEM += '\n' + WORK_POLICY
REVIEW_SYSTEM += '\n' + WORK_POLICY


def _review_ready(state):
    current = (state['planning_creation'].get('inception_review') or {}).get('current') or {}
    return bool(state.get('planning_review_request')) and current.get('id') == state['planning_review_request'] \
        and current.get('status') == 'awaiting_decision'


LOOP = Loop(role='directing', steps='planning_steps', pending='planning_pending', schema=SCHEMA,
            limit='Atingi o limite deste turno; preservei propostas e pareceres. Não há correção em segundo plano.',
            review_ready=_review_ready, not_ready='Ainda não existe uma proposta atual salva para sua revisão.',
            # The Continuity role audits; it does not plan, publish requests or hand work on.
            allowed=lambda state: (('review_continuity', 'read_context', 'read_scene', 'respond')
                                   if state.get('planning_role') == 'continuity'
                                   else tuple(SCHEMA['properties']['action']['enum'])),
            shown=lambda state, action: 'continuity' if action == 'review_continuity'
                                        else state.get('planning_role') or 'directing')


def nodes(model, runtime, auditor=None, reviewer=None):
    """`model` directs; `auditor` serves the Continuity role; `reviewer` the fresh independent review."""

    auditor, reviewer = auditor or model, reviewer or model

    stop = LOOP.stop

    def pack(bundle, scene_id):
        scenes = bundle['production']['scenes']
        bundle = {**bundle, 'work_structure': work_structure(bundle['production'], scene=scene_id),
                  'scope': {'scene': scene_id, 'film_wide': not bool(scene_id),
                  'inspection': 'Canonical/text records only; neighbour scenes are summarized when scoped.'}}
        if scene_id:
            positions = [i for i, item in enumerate(scenes) if item['id'] == scene_id]
            if not positions:
                raise ValueError('No canonical scene with that id')
            at = positions[0]
            nearby = scenes[max(0, at - 1):at + 2]
            # Full target; neighbours retain authored continuity without all take metadata.
            selected = [item if item['id'] == scene_id else {key: item.get(key) for key in
                        ('id', 'title', 'summary', 'direction', 'cast', 'continuity', 'location')} for item in nearby]
            ids = {item['id'] for item in nearby}
            bundle = {**bundle, 'production': {**bundle['production'], 'scenes': selected},
                      'continuity': {**bundle['continuity'], 'scenes': [item for item in bundle['continuity']['scenes'] if item['id'] in ids]}}
        if len(json.dumps(bundle, ensure_ascii=False)) > MAX_CONTEXT:
            raise ValueError('Planning context exceeds the bounded review size; select one narrower scene')
        return bundle

    def context(state):
        try:
            creation = runtime.creation(); bundle = runtime.planning()
            if bundle['project_id'] != creation['project_id'] or bundle['revision'] != creation['revision']:
                raise ValueError('Context changed while being read; retry explicitly')
            decision_id = state.get('resume_decision_id')
            scope = state.get('planning_scene', '')
            if decision_id and not state.get('planning_resume_verified'):
                current = (creation.get('inception_review') or {}).get('current') or {}
                if (current.get('decision') or {}).get('id') != decision_id or current.get('material_changed'):
                    raise ValueError('This direction decision does not match current production material')
                plan_id = current.get('proposal', {}).get('direction_plan')
                if plan_id:
                    scope = next(item['scene'] for item in bundle['direction_plans'] if item['id'] == plan_id)
            bundle = pack(bundle, scope)
            role = state.get('planning_role') or 'directing'
            return {'planning_context': bundle, 'planning_creation': creation, 'planning_scene': scope,
                    'planning_resume_verified': bool(decision_id),
                    'active_role': role, 'agent_status': {'role': role, 'state': 'working'}}
        except Exception as error:
            return stop(state, f'Não consegui ler o contexto de direção/continuidade: {error}')

    def refreshed(state, action, result):
        update = {'planning_pending': {}, 'planning_receipts': [*state.get('planning_receipts', []),
                  {'action': action, 'ok': True, 'result': result}],
                  'production_update': {'id': uuid.uuid4().hex, 'revision': result['revision'], 'kind': action}}
        fresh = context(state)
        if fresh.get('completed_turn'):
            update.update(stop(state, 'A operação foi salva, mas não consegui reler o contexto. Preservei os registros.'))
        else:
            update.update(fresh)
        return update

    def reason(state):
        role = state.get('planning_role') or 'directing'
        bundle = state['planning_context']
        prompt = (f"Canonical pending agent work:\n{production_work(state['planning_creation'])}"
                  f"\nPlanning records and evidence:\n{json.dumps(bundle, ensure_ascii=False)}"
                  f"\nExact human review/direction: {bounded(state['planning_creation'].get('inception_review', {}), 8000)}"
                  f"\nReceipts: {bounded(state.get('planning_receipts', []), 12000)}"
                  f"\nRemaining reasoning steps: {MAX_STEPS-state.get('planning_steps', 0)}; "
                  f"continuity attempts: {MAX_REVIEWS-state.get('planning_reviews', 0)}."
                  '\nConversation:\n' + '\n'.join(f'{m.type}: {m.content}' for m in state['messages'][-10:]))
        if role == 'continuity':
            return step(LOOP, state, auditor, CONTINUITY_SYSTEM, prompt)
        return step(LOOP, state, model, DIRECTING_SYSTEM, prompt)

    def tool(state):
        call = state['planning_pending']; action = call['action']; bundle = state['planning_context']
        tokens = {'expected_revision': bundle['revision'], 'expected_planning_digest': bundle['planning_digest']}
        attempt = 0
        try:
            if action in ('read_context', 'read_scene'):
                scope = call.get('scene') if action == 'read_scene' else state.get('planning_scene', '')
                return {**context({**state, 'planning_scene': scope or ''}), 'planning_pending': {}}
            if action == 'save_plan':
                draft = call.get('draft') or {}
                result = runtime.save_direction_plan({key: draft[key] for key in
                    ('scene', 'title', 'intention', 'shots', 'based_on', 'art_brief') if draft.get(key) is not None} | tokens)
            elif action == 'review_continuity':
                if state.get('planning_reviews', 0) >= MAX_REVIEWS:
                    return stop(state, 'Atingi o limite de revisões; preciso de direção para uma nova rodada.', 'needs_direction')
                plan_id = call.get('plan') or ''
                plan = next((item for item in bundle['direction_plans'] if item['id'] == plan_id), None)
                if plan_id and not plan:
                    raise ValueError('No saved plan with that id; reread the records')
                scope = plan['scene'] if plan else call.get('scene') or state.get('planning_scene', '')
                if state.get('planning_scene') and scope != state['planning_scene']:
                    raise ValueError('Read the addressed scene before reviewing it; current context is scoped elsewhere')
                # Review sees records only, not the creator's conversation or claimed success.
                review_context = {key: bundle[key] for key in ('project_id', 'production', 'continuity', 'evidence', 'scope', 'work_structure')}
                review_context['scope'] = {**bundle['scope'], 'review_scene': scope}
                review_context['plan'] = plan
                review_context['canonical_pending_work'] = json.loads(production_work(state['planning_creation']))
                if plan:
                    review_context['evidence'] = {**bundle['evidence'], 'plan:' + plan_id: {
                        'basis': 'authored', 'description': 'Proposed facts, not canonical or measured facts.'}}
                if len(json.dumps(review_context, ensure_ascii=False)) > MAX_CONTEXT:
                    raise ValueError('Review context too large; select a narrower scene')
                attempt = 1
                review = reviewer.ask(REVIEW_SYSTEM, json.dumps(review_context, ensure_ascii=False), REVIEW_SCHEMA)
                result = runtime.save_continuity_review({key: review.get(key) for key in ('verdict', 'summary', 'findings', 'limitations')} |
                    {'plan': plan_id, 'scene': scope, **tokens})
                return {**refreshed(state, action, result), 'planning_reviews': state.get('planning_reviews', 0) + 1}
            elif action == 'request_review':
                creation = state['planning_creation']; view = creation.get('directing', {})
                plan = next(item for item in view.get('plans', []) if item['id'] == call.get('plan'))
                reviews = [item for item in view.get('reviews', []) if item['plan'] == plan['id']]
                if plan['stale'] or not reviews or reviews[-1]['stale'] or reviews[-1]['verdict'] != 'ready_for_human':
                    raise ValueError('A current successful continuity review is required')
                request = call.get('review_request') or {}
                proposal = {key: request.get(key) for key in ('question', 'scope', 'why', 'next_step')}
                proposal.update(destination='storyboard', direction_plan=plan['id'], continuity_review=reviews[-1]['id'])
                result = runtime.assess_inception({'title': plan['title'], 'summary': reviews[-1]['summary'],
                    'references': [], 'readiness': [{'destination': 'storyboard', 'status': 'ready',
                       'summary': 'Reviewed shot proposal; not canonical promotion or storyboard approval.', 'gaps': []}],
                    'proposal': proposal, 'expected_revision': creation['revision'],
                    'expected_source_digest': creation['source_digest']})
                return {**refreshed(state, action, result), 'planning_review_request': result['assessment']['id']}
            else:
                raise ValueError('Action not authorised')
            return refreshed(state, action, result)
        except Exception as error:
            return {'planning_pending': {}, 'planning_reviews': state.get('planning_reviews', 0) + attempt,
                    'planning_receipts': [*state.get('planning_receipts', []),
                        {'action': action, 'ok': False, 'error': str(getattr(error, 'message', '') or error) or type(error).__name__}],
                    'active_role': state.get('planning_role', 'directing')}

    return context, reason, tool
