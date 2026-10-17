"""Existing Coordinator, retained shot proposals and independent continuity calls."""
from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
import yaml
from pathlib import Path
from unittest.mock import patch

from cine_toaster.creation import creation_view, load_creation
from cine_toaster.creation_review import decide_inception_assessment, inception_source_digest, record_inception_assessment
from cine_toaster.directing import (directing_view, planning_context, save_continuity_review,
                                   save_direction_plan, validate_direction_records)
from cine_toaster.errors import CineToasterError
from cine_toaster.state import Actor
from test_inception_agent import DEMO, HAS_AGENTS, Model, Runtime as BaseRuntime, respond

if HAS_AGENTS:
    from langchain_core.messages import HumanMessage
    from langgraph.checkpoint.memory import MemorySaver
    from cine_toaster.agents.assistant import build
    from cine_toaster.agents.directing import nodes

AGENT = Actor(id='directing', kind='agent')


def draft(scene='SC-010', **extra):
    return {'scene': scene, 'title': 'Listening before the reveal', 'intention': 'Preserve the gradual reveal.',
            'shots': [{'id': 'A', 'label': 'A restrained reveal', 'action': 'The operator listens.',
                       'framing': 'Medium close-up', 'camera_intent': 'Hold the axis and reveal slowly.',
                       'duration_seconds': 8, 'script_units': [1, 2, 3, 4], 'state_in': [], 'state_out': []}], **extra}


def observation(**extra):
    return {'verdict': 'ready_for_human', 'summary': 'The proposed coverage is coherent within this textual scope.',
            'findings': [], 'limitations': ['No rendered camera or images inspected.'], **extra}


class Runtime(BaseRuntime):
    def planning(self):
        return planning_context(self.root)

    def save_direction_plan(self, payload):
        self.writes.append(copy.deepcopy(payload))
        return save_direction_plan(self.root, actor=AGENT, **payload)

    def save_continuity_review(self, payload):
        self.writes.append(copy.deepcopy(payload))
        return save_continuity_review(self.root, actor=Actor(id='continuity', kind='agent'), **payload)


class FilmCase(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / 'film'
        shutil.copytree(DEMO, self.root)
        self.runtime = Runtime(self.root)

    def tokens(self):
        value = planning_context(self.root)
        return {'expected_revision': value['revision'], 'expected_planning_digest': value['planning_digest']}

    def plan(self, **extra):
        return save_direction_plan(self.root, actor=AGENT, **draft(**extra), **self.tokens())['record']

    def review(self, plan='', **extra):
        return save_continuity_review(self.root, plan=plan, actor=AGENT, **observation(**extra), **self.tokens())['record']

    def gate(self, plan, review):
        value = creation_view(self.root)
        return record_inception_assessment(self.root, title='Review the decoupage', summary='A scoped proposal, not storyboard approval.',
            references=[], readiness=[{'destination': 'storyboard', 'status': 'ready', 'summary': 'Proposal only', 'gaps': []}],
            proposal={'destination': 'storyboard', 'question': 'Keep this coverage?', 'scope': 'SC-010 proposal only',
                      'why': 'Coverage reviewed.', 'next_step': 'Develop the proposal, not canonical promotion.',
                      'direction_plan': plan['id'], 'continuity_review': review['id']},
            actor=AGENT, expected_revision=value['revision'], expected_source_digest=value['source_digest'])['assessment']


class DirectingRecordsTests(FilmCase):
    def edit_scene(self, name, **changes):
        path = self.root / 'scenes' / name / 'scene.yaml'
        document = yaml.safe_load(path.read_text()); document.update(changes)
        path.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False))

    def test_linked_scene_with_no_canonical_shots_can_have_a_separate_proposal(self):
        self.edit_scene('010-last-broadcast', shots=[])
        plan = self.plan()
        self.assertEqual(plan['scene'], 'SC-010')
        self.assertEqual(self.runtime.production()['scenes'][0]['shots'], [])

    def test_declared_ledger_state_is_reused_and_source_changes_invalidate_the_report(self):
        self.edit_scene('010-last-broadcast', continuity={'facts': {'radio': 'on'}})
        shots = draft()['shots']; shots[0]['state_in'] = [{'subject': 'radio', 'attribute': 'state', 'value': 'off'}]
        plan = self.plan(shots=shots)
        with self.assertRaises(CineToasterError):
            self.review(plan['id'])
        report = self.review(plan['id'], verdict='needs_changes')
        self.assertEqual(report['checks'][0]['code'], 'proposed_scene_start_conflict')
        self.edit_scene('010-last-broadcast', continuity={'facts': {'radio': 'off'}})
        self.assertTrue(directing_view(self.root)['reviews'][0]['stale'])
        self.assertTrue(directing_view(self.root)['plans'][0]['stale'])

    def test_canonical_continuity_breaks_are_computed_and_explicit_exceptions_are_preserved(self):
        self.edit_scene('010-last-broadcast', continuity={'facts': {'radio': 'on'}})
        self.edit_scene('030-echo-chamber', continuity={'continues': True, 'facts': {'radio': 'off'}})
        with self.assertRaises(CineToasterError):
            self.review(scene='SC-030')
        report = self.review(scene='SC-030', verdict='needs_changes')
        self.assertIn('continuity_break', [item['code'] for item in report['canonical_checks']])
        self.edit_scene('030-echo-chamber', continuity={'continues': True, 'facts': {'radio': 'off'},
            'exceptions': [{'subject': 'radio', 'attribute': 'state', 'reason': 'Intentionally switched between scenes.'}]})
        current = planning_context(self.root)
        self.assertTrue(current['continuity']['scenes'][1]['exceptions'])
        self.assertNotIn('continuity_break', [item['finding']['code'] for item in current['evidence'].values() if 'finding' in item])

    def test_versions_are_retained_and_never_change_canonical_files_or_legacy_material_hash(self):
        original = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        digest = inception_source_digest(self.root, load_creation(self.root))
        first = self.plan(); self.review(first['id']); second = self.plan(based_on=first['id'])
        state = load_creation(self.root); view = directing_view(self.root)
        self.assertEqual(state['direction_plans'], [first, second])
        self.assertFalse(view['plans'][0]['canonical'])
        self.assertTrue(view['reviews'][0]['stale'])
        self.assertEqual(inception_source_digest(self.root, load_creation(self.root)), digest)
        self.assertEqual(state.get('assessment_decisions', []), [])
        for relative, data in original.items():
            self.assertEqual((self.root / relative).read_bytes(), data)

    def test_empty_legacy_creation_loads_without_new_material_or_ledger(self):
        view = creation_view(self.root)
        self.assertEqual(view['directing'], {'planning_digest': None, 'plans': [], 'reviews': []})
        context = planning_context(self.root)
        self.assertIn('continuity:ledger', context['evidence'])
        self.assertEqual(len(context['continuity']['scenes']), 2)

    def test_revision_and_production_source_conflicts_refuse_publication(self):
        tokens = self.tokens(); self.plan()
        with self.assertRaises(CineToasterError):
            save_direction_plan(self.root, actor=AGENT, **draft(), **tokens)
        tokens = self.tokens()
        path = self.root / 'story/screenplay.fountain'
        path.write_text(path.read_text() + '\nA newly declared story beat.\n')
        with self.assertRaises(CineToasterError):
            save_direction_plan(self.root, actor=AGENT, **draft(), **tokens)

    def test_invalid_plan_fields_units_associations_and_lineage_are_refused(self):
        for field, value in [('duration_seconds', float('nan')), ('duration_seconds', True),
                             ('id', '../P1'), ('script_units', [999]), ('script_units', [True]),
                             ('existing_shot', 'not-a-shot'), ('state_in', [{'subject': 'x'}])]:
            with self.subTest(field=field, value=value):
                payload = draft(); payload['shots'][0][field] = value
                with self.assertRaises(CineToasterError):
                    save_direction_plan(self.root, actor=AGENT, **payload, **self.tokens())
        for extra in ({'based_on': 'invented'}, {'art_brief': 'invented'}):
            with self.assertRaises(CineToasterError):
                self.plan(**extra)
        with self.assertRaises(CineToasterError):
            save_direction_plan(self.root, actor=Actor(id='human', kind='human'), **draft(), **self.tokens())

    def test_computed_coverage_and_state_changes_cannot_be_erased_by_the_reviewer(self):
        payload = draft(); payload['shots'][0]['script_units'] = [1, 2]
        plan = self.plan(shots=payload['shots'])
        self.assertEqual(directing_view(self.root)['plans'][0]['checks'][0]['code'], 'proposed_dialogue_uncovered')
        with self.assertRaises(CineToasterError):
            self.review(plan['id'])
        report = self.review(plan['id'], verdict='needs_changes')
        self.assertTrue(report['checks'])
        a = draft()['shots'][0]; b = {**copy.deepcopy(a), 'id': 'B'}
        a['state_out'] = [{'subject': 'operator', 'attribute': 'hand', 'value': 'left'}]
        b['state_in'] = [{'subject': 'operator', 'attribute': 'hand', 'value': 'right'}]
        plan = self.plan(shots=[a, b])
        with self.assertRaises(CineToasterError):
            self.review(plan['id'])
        b['transition_intent'] = 'A visible deliberate change of hand.'
        corrected = self.plan(shots=[a, b], based_on=plan['id'])
        self.assertEqual(self.review(corrected['id'])['checks'], [])

    def test_evidence_basis_and_source_ids_are_verified(self):
        plan = self.plan()
        for finding in [
            {'basis': 'computed', 'sources': ['scene:SC-010']},
            {'basis': 'authored', 'sources': ['invented']},
            {'basis': 'authored', 'sources': []},
        ]:
            with self.assertRaises(CineToasterError):
                self.review(plan['id'], findings=[{'severity': 'advice', 'evidence': 'Claim', 'correction': 'Inspect', **finding}])
        review = self.review(plan['id'], findings=[{'basis': 'authored', 'severity': 'advice',
            'evidence': 'This is proposed coverage, not measured geometry.', 'correction': 'Inspect the camera later.',
            'sources': ['plan:' + plan['id']]}])
        self.assertIn('no pixel inspection', review['limitations'][-1])

    def test_standalone_canonical_continuity_audit_needs_no_shot_plan(self):
        report = self.review(scene='SC-010', verdict='inconclusive')
        self.assertEqual(report['plan'], '')
        self.assertEqual(report['scene'], 'SC-010')
        self.assertFalse(load_creation(self.root).get('direction_plans'))
        with self.assertRaises(CineToasterError):
            self.review(scene='unknown')

    def test_review_scope_must_match_proposal(self):
        plan = self.plan()
        with self.assertRaises(CineToasterError):
            self.review(plan['id'], scene='SC-030')

    def test_new_report_or_proposal_invalidates_pending_human_gate(self):
        plan = self.plan(); review = self.review(plan['id']); gate = self.gate(plan, review)
        self.assertFalse(creation_view(self.root)['inception_review']['current']['material_changed'])
        self.review(plan['id'], verdict='inconclusive')
        self.assertTrue(creation_view(self.root)['inception_review']['current']['material_changed'])
        with self.assertRaises(CineToasterError):
            decide_inception_assessment(self.root, assessment=gate['id'], outcome='approved', guidance='',
                actor=Actor(id='human', kind='human'), expected_revision=load_creation(self.root)['revision'])

    def test_changed_plan_record_is_not_a_current_review(self):
        plan = self.plan(); self.review(plan['id'])
        state = load_creation(self.root); state['direction_plans'][0]['intention'] = 'Changed retained content'
        self.assertTrue(directing_view(self.root, state)['reviews'][0]['stale'])
        state['direction_plans'][0]['based_on'] = 'future-plan'
        with self.assertRaises(ValueError):
            validate_direction_records(state)


@unittest.skipUnless(HAS_AGENTS, 'the agents extra is not installed')
class DirectingGraphTests(FilmCase):
    def turn(self, graph, room='screenplay and storyboard', message_id='one', extra=None, resume=None):
        return graph.invoke({'messages': [HumanMessage(content='Develop the shot proposal', id=message_id)],
            'ag-ui': {'context': [{'description': 'Current room', 'value': room},
                                 {'description': 'Current scene id', 'value': 'SC-010'}, *(extra or [])]},
            **({'resume': {'decision': resume, 'message': message_id}} if resume else {})},
            {'configurable': {'thread_id': 'directing-test'}})

    def last_plan(self):
        return load_creation(self.root)['direction_plans'][-1]['id']

    def review_action(self):
        return {'action': 'review_continuity', 'reply': '', 'plan': self.last_plan()}

    def request_action(self):
        return {'action': 'request_review', 'reply': '', 'plan': self.last_plan(), 'review_request': {
            'question': 'Keep this restrained reveal?', 'scope': 'SC-010 shot proposal only',
            'why': 'Coverage and proposed states were independently reviewed.',
            'next_step': 'Develop the storyboard; no automatic canonical promotion.'}}

    def test_coordinator_delegates_real_work_and_independent_review_before_human_gate(self):
        model = Model({'action': 'delegate_directing', 'reply': ''}, {'action': 'save_plan', 'reply': '', 'draft': draft()},
                      self.review_action, observation(), self.request_action, respond('Proposta salva para sua revisão.', 'needs_review'))
        state = self.turn(build(model, self.runtime, MemorySaver()))
        self.assertEqual(state['agent_status'], {'role': 'directing', 'state': 'needs_review'})
        self.assertEqual(len(load_creation(self.root)['direction_plans']), 1)
        self.assertEqual(len(load_creation(self.root)['continuity_reviews']), 1)
        self.assertEqual(creation_view(self.root)['inception_review']['current']['status'], 'awaiting_decision')
        review_call = model.calls[3]
        self.assertIn('independent Script Supervisor', review_call[0])
        self.assertIn('Work/review unit: the canonical sequence', review_call[0])
        self.assertEqual(json.loads(review_call[1])['work_structure']['sequences'][0]['scene_ids'], ['SC-010', 'SC-030'])
        self.assertNotIn('Conversation:', review_call[1])
        self.assertNotIn('Receipts:', review_call[1])
        self.assertIn('plan:' + self.last_plan(), review_call[1])
        self.assertEqual(load_creation(self.root).get('assessment_decisions', []), [])

    def test_creation_inception_can_handoff_without_another_coordinator(self):
        model = Model({'action': 'delegate_directing', 'reply': '', 'scene': 'SC-030'}, respond('Need an artistic choice.'))
        state = self.turn(build(model, self.runtime), room='creation')
        self.assertEqual(state['active_role'], 'directing')
        self.assertEqual(state['planning_scene'], 'SC-030')
        self.assertIn('Inception specialist', model.calls[0][0])
        self.assertIn('Directing / Shot Planning', model.calls[1][0])

    def test_coordinator_can_delegate_canonical_audit_with_no_new_proposal(self):
        model = Model({'action': 'delegate_continuity', 'reply': ''},
            {'action': 'review_continuity', 'reply': '', 'plan': '', 'scene': 'SC-010'},
            observation(verdict='inconclusive'), respond('Parecer salvo; faltam evidências.', 'complete'))
        state = self.turn(build(model, self.runtime))
        self.assertEqual(state['agent_status']['role'], 'continuity')
        self.assertEqual(load_creation(self.root)['continuity_reviews'][0]['plan'], '')
        self.assertFalse(load_creation(self.root).get('direction_plans'))

    def test_human_changes_resume_exact_proposal_and_preserve_versions(self):
        first = self.plan(); review = self.review(first['id']); gate = self.gate(first, review)
        decision = decide_inception_assessment(self.root, assessment=gate['id'], outcome='changes_requested',
            guidance='Hold the discovery longer.', expected_revision=load_creation(self.root)['revision'],
            actor=Actor(id='director', kind='human'))['decision']
        model = Model({'action': 'save_plan', 'reply': '', 'draft': draft(based_on=first['id'])},
                      self.review_action, observation(), self.request_action, respond('Nova versão salva.', 'needs_review'))
        state = self.turn(build(model, self.runtime), message_id='decision-' + decision['id'],
                          resume=decision['id'])
        self.assertIn('Hold the discovery longer', model.calls[0][1])
        self.assertEqual(len(load_creation(self.root)['direction_plans']), 2)
        self.assertEqual(state['agent_status']['state'], 'needs_review')
        self.assertEqual(len(load_creation(self.root)['assessment_decisions']), 1)

    def test_continuity_role_cannot_author_plans_and_fake_gate_is_refused(self):
        for answers in [({'action': 'delegate_continuity', 'reply': ''}, {'action': 'save_plan', 'reply': '', 'draft': draft()}),
                        ({'action': 'delegate_directing', 'reply': ''}, respond('Approved!', 'needs_review'))]:
            model = Model(*answers)
            state = self.turn(build(model, self.runtime))
            self.assertEqual(state['agent_status']['state'], 'blocked')
            self.assertEqual(self.runtime.writes, [])

    def test_conflict_requires_explicit_reread_and_does_not_refresh_behind_model(self):
        model = Model({'action': 'delegate_directing', 'reply': ''}, {'action': 'save_plan', 'reply': '', 'draft': draft()},
                      respond('Conflito; preciso reler.', 'blocked'))
        with patch.object(self.runtime, 'save_direction_plan', side_effect=ValueError('source conflict')):
            state = self.turn(build(model, self.runtime))
        self.assertFalse(state['planning_receipts'][0]['ok'])
        self.assertIn('source conflict', model.calls[-1][1])
        self.assertFalse(load_creation(self.root).get('direction_plans'))

    def test_review_cannot_use_context_of_a_different_scene(self):
        plan = self.plan(scene='SC-030', shots=[{**draft()['shots'][0], 'script_units': [1, 2, 3, 4, 5]}])
        model = Model({'action': 'delegate_directing', 'reply': ''},
            {'action': 'review_continuity', 'reply': '', 'plan': plan['id']}, respond('Need to read the scene.', 'blocked'))
        state = self.turn(build(model, self.runtime))
        self.assertEqual(len(model.calls), 3)
        self.assertFalse(state['planning_receipts'][-1]['ok'])
        self.assertFalse(load_creation(self.root).get('continuity_reviews'))

    def test_budget_and_replay_do_not_duplicate_writes(self):
        model = Model({'action': 'delegate_directing', 'reply': ''}, *[{'action': 'read_context', 'reply': ''}] * 8)
        graph = build(model, self.runtime, MemorySaver())
        state = self.turn(graph)
        self.assertEqual(state['agent_status']['state'], 'resource_limit')
        calls = len(model.calls); self.turn(graph)
        self.assertEqual(len(model.calls), calls)

    def test_negative_review_can_drive_a_retained_correction_without_a_human_form(self):
        incomplete = draft(); incomplete['shots'][0]['script_units'] = [1, 2]
        def correction():
            return {'action': 'save_plan', 'reply': '', 'draft': draft(based_on=self.last_plan())}
        model = Model({'action': 'delegate_directing', 'reply': ''}, {'action': 'save_plan', 'reply': '', 'draft': incomplete},
            self.review_action, observation(verdict='needs_changes'), correction,
            self.review_action, observation(), self.request_action, respond('Correção pronta.', 'needs_review'))
        state = self.turn(build(model, self.runtime))
        self.assertEqual(state['agent_status']['state'], 'needs_review')
        self.assertEqual(len(load_creation(self.root)['direction_plans']), 2)
        self.assertIn('proposed_dialogue_uncovered', model.calls[4][1])

    def test_fresh_reviewer_failure_saves_no_report_and_approval_does_not_promote(self):
        plan = self.plan()
        model = Model({'action': 'delegate_directing', 'reply': ''}, self.review_action,
            ValueError('Reviewer unavailable'), respond('Não consegui revisar.', 'blocked'))
        state = self.turn(build(model, self.runtime))
        self.assertEqual(state['agent_status']['state'], 'blocked')
        self.assertFalse(load_creation(self.root).get('continuity_reviews'))
        review = self.review(plan['id']); gate = self.gate(plan, review)
        decision = decide_inception_assessment(self.root, assessment=gate['id'], outcome='approved', guidance='',
            actor=Actor(id='director', kind='human'), expected_revision=load_creation(self.root)['revision'])['decision']
        model = Model(respond('A promoção canônica ainda não está implementada.', 'blocked'))
        state = self.turn(build(model, self.runtime), message_id='decision-' + decision['id'],
            resume=decision['id'])
        self.assertEqual(state['active_role'], 'directing')
        self.assertEqual(len(load_creation(self.root)['direction_plans']), 1)
        self.assertEqual(len(self.runtime.production()['scenes'][0]['shots']), 2)

