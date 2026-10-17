"""Explicit sequence work survives without chat and never becomes a fake human gate."""
import copy
import json
import shutil
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from cine_toaster.creation import creation_view, load_creation
from cine_toaster.decision_inbox import decision_inbox
from cine_toaster.errors import CineToasterError, PersistenceError
from cine_toaster.sequence_work import request_sequence_review, sequence_work_view
from cine_toaster.state import Actor
from test_inception_agent import HAS_AGENTS, Model, Runtime

DEMO = Path(__file__).parents[1] / 'examples/demo-project'
AGENT = Actor(id='production-coordinator', kind='agent')


class SequenceWorkTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name) / 'film'
        shutil.copytree(DEMO, self.root)

    def request(self, **changes):
        current = sequence_work_view(self.root)
        return request_sequence_review(self.root, sequence='the-reply', title='Validate The Reply',
            rationale='The director explicitly requested sequence-level Inception/storyboard validation.',
            actor=AGENT, **({'expected_revision': current['revision'],
                            'expected_source_digest': current['source_digest']} | changes))

    def test_missing_drawings_do_not_invent_a_task_or_human_gate(self):
        inbox = decision_inbox(self.root)
        self.assertEqual(inbox['agent_work_count'], 0)
        self.assertEqual(sequence_work_view(self.root)['pending_count'], 0)
        self.assertFalse((self.root / 'creation/state.json').exists())

    def test_request_is_retained_sequence_work_not_approval_or_running_job(self):
        source = creation_view(self.root)['source_digest']
        result = self.request()
        state = load_creation(self.root)
        self.assertEqual(state['sequence_review_requests'][0], result['request'])
        self.assertEqual(result['request']['scene_ids'], ['SC-010', 'SC-030'])
        self.assertEqual(result['request']['owner'], 'coordinator')
        self.assertEqual(result['request']['dispatch_status'], 'not_dispatched')
        self.assertEqual(state.get('assessment_decisions', []), [])
        self.assertEqual(creation_view(self.root)['source_digest'], source)
        view = sequence_work_view(self.root)['items'][0]
        self.assertFalse(view['human_action_required'])
        self.assertFalse(view['execution_supported'])
        self.assertEqual(view['coverage']['shots'], 5)
        self.assertEqual(len(view['coverage']['missing_shots']), 5)
        self.assertIn('sequence_review_capability_missing', [gap['code'] for gap in view['gaps']])
        self.assertEqual(decision_inbox(self.root)['agent_work_count'], 1)
        self.assertEqual(decision_inbox(self.root)['agent_work'][0]['id'], result['request']['id'])

    def test_repeat_is_idempotent_and_stale_revision_is_refused(self):
        result = self.request()
        again = self.request()
        self.assertTrue(again['unchanged'])
        self.assertEqual(again['request'], result['request'])
        self.assertEqual(load_creation(self.root)['revision'], 1)
        with self.assertRaises(CineToasterError):
            self.request(expected_revision=0)

    def test_changed_script_is_visible_and_refresh_preserves_old_request(self):
        first = self.request()['request']
        path = self.root / 'story/screenplay.fountain'
        path.write_text(path.read_text() + '\n\nA final echo.\n')
        item = sequence_work_view(self.root)['items'][0]
        self.assertTrue(item['sources_changed'])
        self.assertEqual(item['next_action'], item['gaps'][0]['next_action'])
        second = self.request()['request']
        self.assertEqual(second['based_on'], first['id'])
        self.assertEqual(load_creation(self.root)['sequence_review_requests'], [first, second])
        self.assertEqual(sequence_work_view(self.root)['pending_count'], 1)

    def test_sequence_reordering_or_removal_never_silently_changes_requested_scope(self):
        from cine_toaster.project import load_production
        self.request()
        production = load_production(self.root)
        production['sequences'][0]['scene_ids'].reverse()
        item = sequence_work_view(self.root, production=production)['items'][0]
        self.assertEqual(item['scene_ids'], ['SC-010', 'SC-030'])
        self.assertEqual(item['current_scene_ids'], ['SC-030', 'SC-010'])
        self.assertTrue(item['scope_changed'])
        self.assertTrue(item['sources_changed'])
        production['sequences'] = []
        item = sequence_work_view(self.root, production=production)['items'][0]
        self.assertEqual(item['current_scene_ids'], [])
        self.assertEqual(item['gaps'][0]['code'], 'scope_unavailable')

    def test_invalid_target_sources_and_actor_cannot_create_work(self):
        view = sequence_work_view(self.root)
        common = {'title': 'Review', 'rationale': 'Requested by the director',
                  'expected_revision': 0, 'expected_source_digest': view['source_digest'], 'actor': AGENT}
        for sequence in ('SC-010', 'The Reply', '../other-film'):
            with self.subTest(sequence=sequence), self.assertRaises(CineToasterError):
                request_sequence_review(self.root, sequence=sequence, **common)
        with self.assertRaises(CineToasterError):
            self.request(expected_source_digest='0' * 64)
        self.assertFalse((self.root / 'creation/state.json').exists())

    def test_journal_corruption_is_not_reported_as_zero_work(self):
        self.request()
        path = self.root / 'creation/state.json'
        original = json.loads(path.read_text())
        for mutate in (lambda state: state.update(sequence_review_requests={}),
                       lambda state: state['sequence_review_requests'][0].update(owner='human'),
                       lambda state: state['sequence_review_requests'][0].update(state='completed'),
                       lambda state: state['sequence_review_requests'][0].update(based_on='missing'),
                       lambda state: state['sequence_review_requests'][0].update(scene_ids=['SC-010', 'SC-010'])):
            changed = copy.deepcopy(original); mutate(changed)
            path.write_text(json.dumps(changed))
            with self.assertRaises(PersistenceError):
                sequence_work_view(self.root)

    @unittest.skipUnless(HAS_AGENTS, 'agents extra is not installed')
    def test_actual_coordinator_and_inception_receive_the_pending_work_automatically(self):
        from cine_toaster.agents.assistant import build
        from langchain_core.messages import HumanMessage
        item = self.request()['request']
        for room in ('overview', 'creation'):
            answer = {'action': 'none', 'reply': 'The sequence review is pending with a capability gap.'} if room == 'overview' else {
                'action': 'respond', 'reply': 'The sequence review is pending with a capability gap.', 'status': 'blocked'}
            model = Model(answer)
            build(model, Runtime(self.root)).invoke({'messages': [HumanMessage(content='What remains?')],
                'ag-ui': {'context': [{'description': 'Current room', 'value': room}]}}, {'recursion_limit': 80})
            self.assertIn(item['id'], model.calls[0][1])
            self.assertIn('sequence_review_capability_missing', model.calls[0][1])
            self.assertIn('SC-030', model.calls[0][1])
        self.assertEqual(load_creation(self.root)['revision'], 1)

    @unittest.skipUnless(HAS_AGENTS, 'agents extra is not installed')
    def test_art_and_directing_receive_canonical_work_not_just_general_policy(self):
        from cine_toaster.agents.assistant import build
        from langchain_core.messages import HumanMessage
        from test_directing_agents import Runtime as PlanningRuntime
        item = self.request()['request']
        for delegation in ('delegate_art_direction', 'delegate_directing', 'delegate_continuity'):
            model = Model({'action': delegation, 'reply': '', 'scene': 'SC-010'},
                          {'action': 'respond', 'reply': 'The whole-sequence task remains pending.', 'status': 'blocked'})
            build(model, PlanningRuntime(self.root)).invoke({'messages': [HumanMessage(content='Inspect the pending sequence work')],
                'ag-ui': {'context': [{'description': 'Current room', 'value': 'overview'}]}}, {'recursion_limit': 80})
            self.assertEqual(len(model.calls), 2)
            self.assertIn(item['id'], model.calls[1][1])
            self.assertIn('sequence_review_capability_missing', model.calls[1][1])
        self.assertEqual(load_creation(self.root)['revision'], 1)

    def test_shared_http_command_exposes_work_and_refuses_conflicts(self):
        from cine_toaster import web
        from cine_toaster.agents.runtime_client import RuntimeClient
        server = ThreadingHTTPServer(('127.0.0.1', 0), web.ProjectBrowserHandler)
        server.project_root = self.root
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(5)))
        client = RuntimeClient(f'http://127.0.0.1:{server.server_port}')
        current = client._call('/api/sequence-work')
        payload = {'sequence': 'the-reply', 'title': 'Validate The Reply', 'rationale': 'Explicit director request.',
                   'expected_revision': current['revision'], 'expected_source_digest': current['source_digest']}
        result = client._call('/api/creation/sequence-review-request', payload)
        inbox = client._call('/api/decisions')
        self.assertEqual(inbox['agent_work_count'], 1)
        self.assertEqual(inbox['agent_work'][0]['id'], result['request']['id'])
        self.assertEqual(result['request']['actor'], {'id': 'production-coordinator', 'kind': 'agent'})
        with self.assertRaises(CineToasterError):
            client._call('/api/creation/sequence-review-request', payload)
