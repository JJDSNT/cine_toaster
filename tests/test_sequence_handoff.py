"""A storyboard request for a whole canonical sequence, the director's unit of review (ADR 0035)."""
from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import yaml

from cine_toaster.creation import creation_view, load_creation
from cine_toaster.decision_inbox import decision_inbox
from cine_toaster.errors import CineToasterError
from cine_toaster.project import load_production
from cine_toaster.stage_handoff import publish_storyboard_reference, sequence_target, target_members
from cine_toaster.storyboard import load_storyboard
from test_stage_handoff import AGENT, HAS_AGENTS, HandoffCase, Model, Runtime, respond

if HAS_AGENTS:
    from langchain_core.messages import HumanMessage
    from langgraph.checkpoint.memory import MemorySaver
    from cine_toaster.agents.assistant import build


class SequenceHandoffCase(HandoffCase):
    def sequence_request(self, sequence='the-reply'):
        return self.assess(scope='The Reply, the whole sequence.', sequence=sequence)

    def publish_at(self, handoff, scene, shot, reference=None):
        return publish_storyboard_reference(self.root, handoff=handoff['id'], scene=scene, shot=shot,
            reference=reference or self.reference, file='drawing.png', title=f'{scene} {shot}', actor=AGENT,
            expected_revision=load_creation(self.root)['revision'],
            expected_storyboard_revision=load_storyboard(self.root)['revision'])


class SequenceHandoffTests(SequenceHandoffCase):
    def test_the_target_is_the_declared_sequence_in_its_declared_order(self):
        path = self.root / 'project.yaml'
        value = yaml.safe_load(path.read_text())
        value['sequences'].append({'id': 'reversed', 'label': 'Reversed', 'scenes': ['SC-030', 'SC-010']})
        path.write_text(yaml.safe_dump(value, allow_unicode=True))
        target = sequence_target(load_production(self.root), 'reversed')
        # Membership and order come from the declaration, never from scene numbers.
        self.assertEqual([part['scene'] for part in target['scenes']], ['SC-030', 'SC-010'])
        self.assertEqual(target_members(target)[0], ('SC-030', 'P1'))
        self.assertIsNone(sequence_target(load_production(self.root), 'no-such-sequence'))

    def test_one_approval_hands_the_whole_sequence_to_art_direction(self):
        self.sequence_request()
        preview = creation_view(self.root)['inception_review']['current']['handoff_preview']
        self.assertTrue(preview['can_advance'])
        self.assertEqual(preview['target']['sequence'], 'the-reply')
        handoff = self.advance()['handoff']
        self.assertEqual(len(target_members(handoff['target'])), 5)
        view = creation_view(self.root)['handoffs'][0]
        self.assertEqual(view['coverage'], {'shots': 5, 'drawn': 0})
        self.assertEqual(len(view['missing']), 5)
        work = decision_inbox(self.root)['agent_work'][0]
        self.assertEqual(work['coverage'], {'shots': 5, 'drawn': 0})

    def test_drawings_land_in_any_scene_of_the_sequence_and_nowhere_else(self):
        self.sequence_request()
        handoff = self.advance()['handoff']
        self.publish_at(handoff, 'SC-030', 'P2')
        self.assertEqual(creation_view(self.root)['handoffs'][0]['coverage'], {'shots': 5, 'drawn': 1})
        with self.assertRaises(CineToasterError):
            self.publish_at(handoff, 'SC-030', 'P9')

    def test_a_sequence_request_retires_the_scene_study_from_the_work_list(self):
        self.assess()
        self.advance()
        self.assertEqual(len(decision_inbox(self.root)['agent_work']), 1)
        self.sequence_request()
        self.advance()
        work = decision_inbox(self.root)['agent_work']
        self.assertEqual(len(work), 1)
        self.assertEqual(work[0]['coverage'], {'shots': 5, 'drawn': 0})
        self.assertTrue(creation_view(self.root)['handoffs'][0]['superseded'])  # kept as history

    def test_partly_drawn_is_still_work(self):
        self.sequence_request()
        handoff = self.advance()['handoff']
        self.publish_at(handoff, 'SC-010', 'P1')
        self.assertEqual(decision_inbox(self.root)['agent_work'][0]['state'], 'awaiting_agent_output')

    def test_a_scene_study_is_still_a_scene_study(self):
        self.assess()  # 'SC-010 / P1 only.'
        target = creation_view(self.root)['inception_review']['current']['handoff_preview']['target']
        self.assertEqual(target, {'scene': 'SC-010', 'shots': ['P1']})

    def test_a_forged_or_outdated_sequence_target_is_never_authority(self):
        self.assess(target={'sequence': 'the-reply', 'scenes': [{'scene': 'SC-010', 'shots': ['P1']}]})
        self.assertFalse(creation_view(self.root)['inception_review']['current']['handoff_preview']['can_advance'])


@unittest.skipUnless(HAS_AGENTS, 'the agents extra is not installed')
class SequenceArtTests(SequenceHandoffCase):
    def graph(self, *answers, waits=None):
        self.model = Model(*answers)
        return build(self.model, self.runtime, MemorySaver(), waits=waits)

    def continue_approved(self, graph, decision, thread='seq'):
        message = 'decision-' + decision
        return graph.invoke({'messages': [HumanMessage(content='Continue approved work', id=message)],
                             'resume': {'decision': decision, 'message': message}},
                            {'configurable': {'thread_id': thread}})

    def brief(self):
        from cine_toaster.art_direction import save_art_brief
        value = creation_view(self.root)
        return save_art_brief(self.root, title='The Reply boards', text='Ink boards for the whole sequence.',
                              criteria=['Each shot reads at a glance.'], references=[self.reference], actor=AGENT,
                              expected_revision=value['revision'], expected_source_digest=value['source_digest'])['record']

    def test_art_direction_sees_the_whole_sequence_and_focuses_the_first_scene_missing_drawings(self):
        self.sequence_request()
        decision = self.advance()['decision']['id']
        self.publish_at(creation_view(self.root)['handoffs'][0], 'SC-010', 'P1')
        self.publish_at(creation_view(self.root)['handoffs'][0], 'SC-010', 'P2')
        graph = self.graph(respond('Lido.', 'complete'))
        self.continue_approved(graph, decision)
        prompt = self.model.calls[0][1]
        self.assertIn('"sequence": "the-reply"', prompt)
        self.assertIn('"focus": "SC-030"', prompt)  # SC-010 is drawn: the work moves on

    def test_one_consent_sends_the_whole_batch_and_every_job_is_left_to_operations(self):
        from cine_toaster.agents.operations import WaitStore

        self.sequence_request()
        decision = self.advance()['decision']['id']
        brief = self.brief()
        items = [{'scene': scene, 'shot': shot, 'title': f'{scene} {shot}', 'request': 'Draw it.',
                  'parents': [self.reference]} for scene, shot in target_members(
                      creation_view(self.root)['handoffs'][0]['target'])]
        waits = WaitStore(self.root.parent / 'waits.json')
        graph = self.graph({'action': 'plan_batch', 'reply': '', 'brief': brief['id'], 'batch': items},
                           {'action': 'generate', 'reply': ''}, waits=waits)
        started = []

        def start(plan):
            started.append(plan['title'])
            return {'id': f'job_{len(started)}'}

        self.runtime.plan_reference = lambda payload: {**payload, 'available': True, 'prompt': payload['request']}
        self.runtime.start_reference = start
        self.runtime.job = lambda identity: {'id': identity, 'state': 'running', 'kind': 'generate_reference'}
        config = {'configurable': {'thread_id': 'seq'}}
        first = self.continue_approved(graph, decision)
        interrupt = first['__interrupt__'][0].value
        self.assertIn('5 desenhos', interrupt['message'])  # one question for the whole batch
        self.assertEqual(started, [])                      # nothing sent before the consent
        from langgraph.types import Command
        with patch('cine_toaster.agents.art.WAIT_SECONDS', 0):
            state = graph.invoke(Command(resume={'approved': True}), config)
        self.assertEqual(len(started), 5)
        self.assertEqual(state['agent_status']['state'], 'waiting_for_job')
        self.assertEqual({item['job'] for item in waits.all()}, {f'job_{n}' for n in range(1, 6)})
        self.assertEqual(state['art_batch']['job_3']['scene'], items[2]['scene'])

    def test_a_batch_item_outside_the_approved_sequence_is_refused(self):
        self.sequence_request()
        decision = self.advance()['decision']['id']
        brief = self.brief()
        graph = self.graph({'action': 'plan_batch', 'reply': '', 'brief': brief['id'], 'batch': [
                               {'scene': 'SC-030', 'shot': 'P9', 'title': 'x', 'request': 'x', 'parents': []}]},
                           respond('Recusado.', 'blocked'))
        self.runtime.plan_reference = lambda payload: self.fail('planned outside the handoff')
        state = self.continue_approved(graph, decision)
        self.assertFalse(state['art_receipts'][0]['ok'])
        self.assertIn('approved handoff', state['art_receipts'][0]['error'])


if __name__ == '__main__':
    unittest.main()
