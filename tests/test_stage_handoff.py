"""Human-owned promotion, retained inputs/outputs and a derived decision inbox."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from cine_toaster.creation import creation_view, load_creation, save_creation_draft
from cine_toaster.creation_review import decide_inception_assessment, record_inception_assessment
from cine_toaster.decision_inbox import decision_inbox
from cine_toaster.errors import CineToasterError
from cine_toaster.references import add_reference
from cine_toaster.stage_handoff import publish_storyboard_reference, validate_handoffs
from cine_toaster.state import Actor
from cine_toaster.storyboard import load_storyboard
from test_inception_agent import DEMO, HAS_AGENTS, Model, Runtime as BaseRuntime, respond

AGENT = Actor(id='art-direction', kind='agent')
HUMAN = Actor(id='director', kind='human')

if HAS_AGENTS:
    from langchain_core.messages import HumanMessage
    from langgraph.checkpoint.memory import MemorySaver
    from cine_toaster.agents.assistant import build


class Runtime(BaseRuntime):
    def storyboard(self, scene=''):
        from cine_toaster.storyboard import storyboard_view
        return storyboard_view(self.root, scene)

    def publish_storyboard(self, payload):
        self.writes.append(copy.deepcopy(payload))
        return publish_storyboard_reference(self.root, actor=AGENT, **payload)


class HandoffCase(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / 'film'; shutil.copytree(DEMO, self.root)
        picture = Path(directory.name) / 'drawing.png'; Image.new('RGB', (32, 32), 'red').save(picture)
        self.reference = add_reference(self.root, [picture], title='Synthetic drawing fixture', kind='made').name
        self.runtime = Runtime(self.root)

    def assess(self, scope='SC-010 / P1 only.', **extra):
        value = creation_view(self.root)
        return record_inception_assessment(self.root, title='Develop the opening', summary='Enough to develop one opening drawing.',
            references=[self.reference], readiness=[{'destination': 'storyboard', 'status': 'ready', 'summary': 'Development only', 'gaps': []}],
            proposal={'destination': 'storyboard', 'question': 'Develop this opening?', 'scope': scope, 'why': 'Clear intent.',
                      'next_step': 'Develop a retained opening drawing; preserve alternatives.', **extra},
            expected_revision=value['revision'], actor=AGENT)['assessment']

    def advance(self):
        value = creation_view(self.root); current = value['inception_review']['current']
        return decide_inception_assessment(self.root, assessment=current['id'], outcome='approved', guidance='',
            expected_revision=value['revision'], actor=HUMAN, advance=True,
            expected_handoff_digest=current['handoff_preview']['sha256'])

    def publish(self, handoff, **extra):
        return publish_storyboard_reference(self.root, handoff=handoff['id'], scene='SC-010', shot='P1',
            reference=self.reference, file='drawing.png', title='First storyboard pass', actor=AGENT,
            expected_revision=load_creation(self.root)['revision'], expected_storyboard_revision=load_storyboard(self.root)['revision'], **extra)


class HandoffTests(HandoffCase):
    def test_pending_request_is_visible_without_becoming_a_blanket_missing_artifact_queue(self):
        self.assertEqual(decision_inbox(self.root)['pending_count'], 0)
        saved = self.assess(); inbox = decision_inbox(self.root)
        self.assertEqual(inbox['pending_count'], 1)
        self.assertEqual(inbox['items'][0]['id'], saved['id'])
        self.assertEqual(inbox['items'][0]['target'], {'scene': 'SC-010', 'shots': ['P1']})
        self.assertIn('#direction-review', inbox['items'][0]['url'])

    def test_approval_atomically_promotes_exact_inputs_without_approving_storyboard(self):
        self.assess(); before = load_creation(self.root)['revision']; result = self.advance()
        state = load_creation(self.root)
        self.assertEqual(state['revision'], before + 1)
        self.assertEqual(state['stage_handoffs'][0]['decision'], result['decision']['id'])
        self.assertEqual(decision_inbox(self.root)['pending_count'], 0)
        self.assertEqual(decision_inbox(self.root)['agent_work'][0]['state'], 'awaiting_agent_output')
        self.assertEqual(load_storyboard(self.root)['candidates'], [])
        self.assertEqual(result['decision']['next_agent_action']['status'], 'not_dispatched')
        self.assertFalse(creation_view(self.root)['handoffs'][0]['stale'])

    def test_wrong_preview_or_agent_actor_cannot_approve_or_promote(self):
        saved = self.assess(); value = creation_view(self.root)
        for actor, token in ((AGENT, value['inception_review']['current']['handoff_preview']['sha256']), (HUMAN, 'invented')):
            with self.assertRaises(CineToasterError):
                decide_inception_assessment(self.root, assessment=saved['id'], outcome='approved', guidance='',
                    expected_revision=value['revision'], actor=actor, advance=True, expected_handoff_digest=token)
        self.assertFalse(load_creation(self.root).get('assessment_decisions'))
        self.assertFalse(load_creation(self.root).get('stage_handoffs'))

    def test_ambiguous_legacy_scope_is_not_silently_promoted(self):
        self.assess(scope='Develop the opening.')
        self.assertFalse(creation_view(self.root)['inception_review']['current']['handoff_preview']['can_advance'])
        with self.assertRaises(CineToasterError):
            self.advance()
        self.assertFalse(load_creation(self.root).get('assessment_decisions'))

    def test_output_is_retained_linked_and_replay_is_idempotent(self):
        self.assess(); handoff = self.advance()['handoff']; result = self.publish(handoff)
        again = self.publish(handoff)
        self.assertEqual(result['candidate']['id'], again['candidate']['id'])
        self.assertTrue(again['replayed'])
        self.assertEqual(len(load_storyboard(self.root)['candidates']), 1)
        self.assertEqual(result['candidate']['provenance']['handoff'], handoff['id'])
        self.assertEqual(result['candidate']['inputs'][0]['id'], self.reference)
        self.assertFalse(creation_view(self.root)['handoffs'][0]['stale'])
        self.assertEqual(decision_inbox(self.root)['agent_work'][0]['state'], 'outputs_retained')

    def test_additive_work_is_allowed_but_changed_pinned_sources_refuse_consumption(self):
        self.assess(); handoff = self.advance()['handoff']
        save_creation_draft(self.root, kind='concept', title='Additive downstream study', text='A later exploration.',
                            expected_revision=load_creation(self.root)['revision'], actor=AGENT)
        self.assertFalse(creation_view(self.root)['handoffs'][0]['stale'])
        self.publish(handoff)
        path = self.root / 'references' / self.reference / 'drawing.png'
        Image.new('RGB', (32, 32), 'blue').save(path)
        self.assertTrue(creation_view(self.root)['handoffs'][0]['stale'])
        with self.assertRaises(CineToasterError):
            self.publish(handoff)

    def test_out_of_scope_target_path_and_revision_are_refused(self):
        self.assess(); handoff = self.advance()['handoff']; value = load_creation(self.root)
        base = {'handoff': handoff['id'], 'scene': 'SC-010', 'shot': 'P1', 'reference': self.reference,
                'file': 'drawing.png', 'title': 'A draft', 'actor': AGENT, 'expected_revision': value['revision'], 'expected_storyboard_revision': 0}
        for extra in ({'shot': 'P2'}, {'scene': 'SC-030'}, {'file': '../../project.yaml'},
                      {'expected_revision': 0}, {'actor': HUMAN}, {'expected_revision': True}):
            with self.assertRaises(CineToasterError):
                publish_storyboard_reference(self.root, **(base | extra))
        self.assertEqual(load_storyboard(self.root)['candidates'], [])

    def test_changed_canonical_script_invalidates_handoff_and_stale_request_is_not_actionable(self):
        self.assess(); handoff = self.advance()['handoff']
        path = self.root / 'story/screenplay.fountain'; path.write_text(path.read_text() + '\nNew story beat.\n')
        self.assertTrue(creation_view(self.root)['handoffs'][0]['stale'])
        self.assertEqual(decision_inbox(self.root)['pending_count'], 0)
        with self.assertRaises(CineToasterError):
            self.publish(handoff)

    def test_rejection_never_creates_a_promoted_input(self):
        saved = self.assess(); value = creation_view(self.root)
        decide_inception_assessment(self.root, assessment=saved['id'], outcome='changes_requested', guidance='Use a quieter discovery.',
                                    expected_revision=value['revision'], actor=HUMAN)
        self.assertFalse(load_creation(self.root).get('stage_handoffs'))

    def test_failed_atomic_commit_keeps_both_approval_and_handoff_absent(self):
        self.assess(); original = load_creation(self.root)
        with patch('cine_toaster.creation_review._commit', side_effect=OSError('Synthetic write failure')):
            with self.assertRaises(OSError):
                self.advance()
        self.assertEqual(load_creation(self.root), original)

    def test_inbox_includes_real_waiting_scene_gates_but_not_approved_ones(self):
        production = self.runtime.production(); scene = production['scenes'][0]
        scene['gates'] = {'pending': {'state': 'waiting', 'kind': 'approve_picture', 'subject': 'P1', 'candidates': ['a']},
                          'decided': {'state': 'approved', 'kind': 'approve_picture', 'subject': 'P2'}}
        with patch('cine_toaster.decision_inbox.load_production', return_value=production):
            inbox = decision_inbox(self.root)
        self.assertEqual(inbox['pending_count'], 1)
        self.assertEqual(inbox['items'][0]['id'], 'pending')
        self.assertEqual(inbox['items'][0]['evidence']['candidates'], ['a'])

    def test_output_review_is_not_a_second_generate_handoff(self):
        self.assess(review_kind='storyboard_candidates', target={'scene': 'SC-010', 'shots': ['P1']})
        self.assertFalse(creation_view(self.root)['inception_review']['current']['handoff_preview']['can_advance'])
        with self.assertRaises(CineToasterError):
            self.advance()

    def test_second_versions_preserve_prior_images_and_corrupt_handoff_is_not_empty(self):
        self.assess(); handoff = self.advance()['handoff']; first = self.publish(handoff)['candidate']
        pixels = (self.root / first['image']['path']).read_bytes()
        self.publish(handoff, based_on=first['id'])
        self.assertEqual(len(load_storyboard(self.root)['candidates']), 2)
        self.assertEqual((self.root / first['image']['path']).read_bytes(), pixels)
        state = load_creation(self.root); state['stage_handoffs'][0]['sources']['production'] = 'tampered'
        with self.assertRaises(ValueError):
            validate_handoffs(state)


@unittest.skipUnless(HAS_AGENTS, 'the agents extra is not installed')
class HandoffAgentTests(HandoffCase):
    def test_explicit_fresh_continuation_can_resume_after_a_bounded_stop_but_replay_cannot(self):
        self.assess(); result = self.advance(); decision = result['decision']['id']
        model = Model(respond('Need another bounded pass.', 'blocked'), respond('A new explicitly requested turn.', 'blocked'))
        graph = build(model, self.runtime, MemorySaver())
        def turn(attempt):
            message = 'decision-' + decision + '-' + attempt
            return graph.invoke({'messages': [HumanMessage(content='Continue approved work', id=message)],
                'resume': {'decision': decision, 'message': message}},
                {'configurable': {'thread_id': 'manual-continuation'}})
        turn('retry-one'); turn('retry-one')
        self.assertEqual(len(model.calls), 1)
        turn('retry-two')
        self.assertEqual(len(model.calls), 2)
        self.assertEqual(len(load_creation(self.root)['stage_handoffs']), 1)

    def test_approved_direction_routes_to_existing_art_role_and_publishes_a_real_drawing(self):
        self.assess(); result = self.advance(); decision = result['decision']['id']
        model = Model({'action': 'save_storyboard', 'reply': '', 'board': {
            'scene': 'SC-010', 'shot': 'P1', 'reference': self.reference, 'file': 'drawing.png', 'title': 'Opening draft'}},
            respond('Desenho retido; revisão visual ainda pendente.', 'complete'))
        graph = build(model, self.runtime)
        state = graph.invoke({'messages': [HumanMessage(content='Continue approved direction', id='decision-' + decision)],
            'ag-ui': {'context': [{'description': 'Current room', 'value': 'decisions'}]},
            'resume': {'decision': decision, 'message': 'decision-' + decision}})
        self.assertEqual(state['active_role'], 'art_direction')
        self.assertIn('Art Direction specialist', model.calls[0][0])
        self.assertIn(result['handoff']['id'], model.calls[0][1])
        self.assertEqual(len(load_storyboard(self.root)['candidates']), 1)
        self.assertEqual(len(load_creation(self.root)['assessment_decisions']), 1)

