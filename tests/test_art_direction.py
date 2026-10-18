"""Retained art work, actual raster transport and the existing agent/job loop."""
from __future__ import annotations

import base64
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from cine_toaster.art_direction import image_package, save_art_brief, save_visual_review
from cine_toaster.creation import creation_view, load_creation
from cine_toaster.creation_review import record_inception_assessment
from cine_toaster.errors import CineToasterError
from cine_toaster.new_production import create_production
from cine_toaster.references import add_reference
from cine_toaster.state import Actor

from test_inception_agent import HAS_AGENTS, Runtime as InceptionRuntime

if HAS_AGENTS:
    from langchain_core.messages import HumanMessage
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command
    from cine_toaster.agents.assistant import build

AGENT = Actor(id='art-direction', kind='agent')
CRITERION = 'The red circle is clearly legible on a dark background.'


def observation(status='pass'):
    return {'summary': 'A clear visual candidate.', 'verdict': 'ready_for_human' if status == 'pass' else 'needs_changes',
            'findings': [{'criterion': CRITERION, 'status': status,
                          'evidence': 'The red circle contrasts with the black background.',
                          'correction': 'Keep this contrast.' if status == 'pass' else 'Increase the circle size.'}]}


class FilmCase(unittest.TestCase):
    def assertShowsThePicture(self, image):
        """The reviewer sees a reduced copy of the registered picture, pinned by the original's digest."""
        import hashlib
        import io

        self.assertEqual(image['sha256'], hashlib.sha256(self.picture.read_bytes()).hexdigest())
        with Image.open(io.BytesIO(base64.b64decode(image['data']))) as shown:
            self.assertEqual(shown.size, (32, 32))
            red, green, blue = shown.convert('RGB').getpixel((16, 16))
            self.assertGreater(red, 200)
            self.assertLess(green + blue, 60)

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = create_production(Path(directory.name) / 'film', 'Shapes').root
        picture = Path(directory.name) / 'candidate.png'
        Image.new('RGB', (32, 32), 'red').save(picture)
        self.picture = picture
        self.reference = add_reference(self.root, [picture], title='First candidate', kind='made').name

    def tokens(self):
        value = creation_view(self.root)
        return {'expected_revision': value['revision'], 'expected_source_digest': value['source_digest']}

    def brief(self, **extra):
        return save_art_brief(self.root, title='Red identity', text='A vivid red circular motif.', criteria=[CRITERION],
                              references=[self.reference], actor=AGENT, **self.tokens(), **extra)['record']

    def review(self, brief, **extra):
        package = image_package(self.root, [self.reference])
        return save_visual_review(self.root, brief=brief['id'], references=[self.reference],
            images_digest=package['images_digest'], actor=Actor(id='visual-prevalidation', kind='agent'),
            **self.tokens(), **(observation() | extra))['record']


class ArtRecordsTests(FilmCase):
    def test_versions_and_independent_reviews_survive_reload_without_approval(self):
        first = self.brief(); review = self.review(first)
        view = creation_view(self.root)
        self.assertFalse(view['art_direction']['reviews'][0]['stale'])
        self.assertFalse(view['art_direction']['reviews'][0]['human_approval'])
        self.brief(based_on=first['id'])
        state = load_creation(self.root)
        self.assertEqual(len(state['art_briefs']), 2)
        self.assertEqual(state['visual_reviews'][0]['id'], review['id'])
        self.assertTrue(creation_view(self.root)['art_direction']['reviews'][0]['stale'])
        self.assertEqual(state.get('assessment_decisions', []), [])
        self.assertEqual(len(list((self.root / 'references').iterdir())), 1)

    def test_changed_material_and_revision_refuse_writes(self):
        tokens = self.tokens(); self.brief()
        with self.assertRaises(CineToasterError):
            save_art_brief(self.root, title='Conflict', text='Do not overwrite.', criteria=[CRITERION],
                           references=[], actor=AGENT, **tokens)
        tokens = self.tokens()
        (self.root / 'story/screenplay.fountain').write_text('Title: Changed\n\nA new intention.\n')
        with self.assertRaises(CineToasterError):
            save_art_brief(self.root, title='Conflict', text='Do not overwrite.', criteria=[CRITERION],
                           references=[], actor=AGENT, **tokens)

    def test_real_pixels_are_bounded_and_registered_not_arbitrary_paths(self):
        package = image_package(self.root, [self.reference])
        self.assertShowsThePicture(package['images'][0])
        for invalid in ([], ['../../etc/passwd'], [self.reference] * 5):
            with self.assertRaises(CineToasterError):
                image_package(self.root, invalid)

    def test_changed_pixels_refuse_inspection(self):
        brief = self.brief()
        package = image_package(self.root, [self.reference])
        folder = self.root / 'references' / self.reference
        raster = next(folder.glob('*.png'))
        raster.write_bytes(b'changed')
        with self.assertRaises(CineToasterError):
            image_package(self.root, [self.reference])
        self.assertEqual(load_creation(self.root)['art_briefs'][0]['id'], brief['id'])
        self.assertTrue(package['images_digest'])

    def test_a_batch_review_marks_what_it_does_not_hold(self):
        from cine_toaster.art_direction import _review_fields
        brief = {'criteria': ['P1 reads as ink', 'P7 shows the summit']}
        held = {'criterion': 'P1 reads as ink', 'status': 'pass', 'evidence': 'Ink line.', 'correction': 'None.'}
        other = {'criterion': 'P7 shows the summit', 'status': 'not_in_batch', 'evidence': 'P7 not attached.',
                 'correction': 'Reviewed in another batch.'}
        _review_fields(brief, 'ready_for_human', [held, other], 'Batch passes.')
        with self.assertRaises(CineToasterError):  # a batch holding nothing proves nothing
            _review_fields(brief, 'ready_for_human', [{**held, 'status': 'not_in_batch'}, other], 'Empty.')

    def test_failed_or_uncertain_findings_cannot_claim_readiness(self):
        brief = self.brief()
        for status in ('fail', 'uncertain'):
            bad = observation(status); bad['verdict'] = 'ready_for_human'
            with self.assertRaises(CineToasterError):
                self.review(brief, **bad)
        self.assertEqual(load_creation(self.root).get('visual_reviews', []), [])

    def test_forged_image_digest_refuses_publication(self):
        brief = self.brief()
        with self.assertRaises(CineToasterError):
            save_visual_review(self.root, brief=brief['id'], references=[self.reference], images_digest='invented',
                               actor=AGENT, **self.tokens(), **observation())

    def test_generation_plan_pins_brief_and_criteria(self):
        from cine_toaster.creation_jobs import plan_reference
        brief = self.brief()
        with patch('cine_toaster.creation_jobs.image_providers', return_value={'codex-image': lambda: SimpleNamespace(binary='/fake')}):
            plan = plan_reference(self.root, {'title': 'Version two', 'request': 'Develop this motif.',
                                             'parents': [self.reference], 'art_brief': brief['id']})
            self.assertIn(CRITERION, plan['prompt'])
            self.assertEqual(plan['inputs'][-1]['kind'], 'art_brief')
            self.assertEqual(plan_reference(self.root, plan), plan)

    def test_prior_human_request_becomes_stale_after_brief_correction(self):
        first = self.brief(); review = self.review(first)
        record_inception_assessment(self.root, title='Visual choice', summary='Review this motif.',
            readiness=[{'destination': 'storyboard', 'status': 'ready', 'summary': 'A candidate exists.', 'gaps': []}],
            proposal={'destination': 'storyboard', 'question': 'Use this motif?', 'scope': 'Only this motif.',
                      'why': 'It fits the intention.', 'next_step': 'Develop boards.', 'visual_review': review['id'],
                      'art_brief': first['id']}, references=[self.reference], actor=AGENT, **self.tokens())
        self.assertEqual(creation_view(self.root)['inception_review']['current']['status'], 'awaiting_decision')
        self.brief(based_on=first['id'])
        self.assertEqual(creation_view(self.root)['inception_review']['current']['status'], 'needs_reassessment')

    def test_an_unusable_raster_is_not_a_metadata_only_pass(self):
        invalid = self.root.parent / 'not-an-image.png'; invalid.write_bytes(b'not an image')
        ref = add_reference(self.root, [invalid], title='Broken raster', kind='made').name
        with self.assertRaises(CineToasterError):
            image_package(self.root, [ref])


class Runtime(InceptionRuntime):
    def save_art_brief(self, payload):
        return save_art_brief(self.root, actor=AGENT, **payload)

    def visual_images(self, references):
        return image_package(self.root, references)

    def save_visual_review(self, payload):
        return save_visual_review(self.root, actor=Actor(id='visual-prevalidation', kind='agent'), **payload)

    def plan_reference(self, payload):
        from cine_toaster.creation_jobs import plan_reference
        return plan_reference(self.root, payload)

    def start_reference(self, plan):
        return self.manager.submit('generate_reference', self.root, {**plan, 'accept_quota': True})

    def job(self, job_id):
        return self.manager.get(job_id)

    def keep_reference(self, job_id):
        return self.manager.adopt(job_id, overwrite=False)


class Model:
    name = 'independent-art-test-provider'

    def __init__(self, *answers, visual=None):
        self.answers = list(answers); self.calls = []; self.images = []
        self.visual = visual or observation()

    def ask(self, system, prompt, schema):
        self.calls.append((system, prompt))
        answer = self.answers.pop(0)
        return answer() if callable(answer) else copy.deepcopy(answer)

    def ask_images(self, system, prompt, schema, images):
        self.images.append((system, prompt, images))
        return copy.deepcopy(self.visual)


@unittest.skipUnless(HAS_AGENTS, 'Install the agents extra')
class ArtAgentTests(FilmCase):
    def graph(self, *answers, visual=None):
        model = Model({'action': 'delegate_art_direction', 'reply': ''}, *answers, visual=visual)
        runtime = Runtime(self.root)
        return build(model, runtime, MemorySaver()), model, runtime

    def invoke(self, graph, text='Develop art direction'):
        return graph.invoke({'messages': [HumanMessage(content=text, id='art-turn')],
                             'ag-ui': {'context': [{'description': 'Current room', 'value': 'creation'}]}},
                            {'configurable': {'thread_id': 'art-test'}})

    def test_inception_delegates_real_brief_then_independent_pixel_review_and_human_gate(self):
        graph, model, _ = self.graph(
            {'action': 'save_brief', 'draft': {'title': 'Motif', 'text': 'A circular red motif.',
               'criteria': [CRITERION], 'references': [self.reference]}},
            lambda: {'action': 'inspect', 'brief': load_creation(self.root)['art_briefs'][-1]['id'], 'references': [self.reference]},
            lambda: {'action': 'request_review', 'brief': load_creation(self.root)['art_briefs'][-1]['id']},
            {'action': 'respond', 'reply': 'Ready for your creative review.', 'status': 'needs_review'})
        state = self.invoke(graph)
        self.assertEqual(state['agent_status']['state'], 'needs_review')
        saved = load_creation(self.root)
        self.assertEqual(len(saved['art_briefs']), 1)
        self.assertEqual(len(saved['visual_reviews']), 1)
        self.assertEqual(saved['assessments'][-1]['proposal']['visual_review'], saved['visual_reviews'][0]['id'])
        self.assertEqual(saved.get('assessment_decisions', []), [])
        self.assertEqual(len(model.images), 1)
        self.assertIn('Work/review unit: the canonical sequence', model.images[0][0])
        self.assertIn('Canonical work structure:', json.loads(model.images[0][1])['film'])
        self.assertIn('"project_id": "shapes"', json.loads(model.images[0][1])['film'])
        self.assertNotIn('Conversation:', model.images[0][1])
        self.assertShowsThePicture(model.images[0][2][0])
        self.assertEqual(creation_view(self.root)['inception_review']['current']['status'], 'awaiting_decision')

    def test_failed_review_drives_preserved_brief_correction(self):
        first = self.brief()
        graph, model, _ = self.graph(
            {'action': 'inspect', 'brief': first['id'], 'references': [self.reference]},
            {'action': 'save_brief', 'draft': {'title': 'Corrected motif', 'text': 'Increase circle size.',
               'criteria': [CRITERION], 'references': [self.reference], 'based_on': first['id']}},
            {'action': 'respond', 'reply': 'Prepared correction; no image generation authorised.', 'status': 'complete'},
            visual=observation('fail'))
        self.invoke(graph)
        self.assertEqual(len(load_creation(self.root)['art_briefs']), 2)
        self.assertEqual(load_creation(self.root)['visual_reviews'][0]['verdict'], 'needs_changes')
        self.assertIn('Increase the circle size', model.calls[-1][1])

    def test_text_only_provider_cannot_claim_pixel_inspection(self):
        brief = self.brief()
        graph, model, _ = self.graph({'action': 'inspect', 'brief': brief['id'], 'references': [self.reference]},
                                    {'action': 'respond', 'reply': 'Vision unavailable.', 'status': 'blocked'})
        model.ask_images = None
        state = self.invoke(graph)
        self.assertEqual(state['agent_status']['state'], 'blocked')
        self.assertEqual(load_creation(self.root).get('visual_reviews', []), [])
        self.assertIn('não recebe imagens', str(state['messages'][-1].content))

    def test_a_role_bound_reviewer_inspects_with_its_own_model(self):
        brief = self.brief()
        creator = Model({'action': 'delegate_art_direction', 'reply': ''},
                        {'action': 'inspect', 'brief': brief['id'], 'references': [self.reference]},
                        {'action': 'respond', 'reply': 'Reviewed.', 'status': 'complete'})
        creator.ask_images = None  # the creator's model is text-only; the person bound the reviewer to another
        reviewer = Model()
        graph = build(creator, Runtime(self.root), MemorySaver(),
                      models=lambda role: reviewer if role == 'visual_prevalidation' else creator)
        state = self.invoke(graph)
        self.assertEqual(state['agent_status']['state'], 'complete')
        self.assertEqual(len(reviewer.images), 1)
        self.assertEqual(reviewer.calls, [])
        self.assertEqual(len(load_creation(self.root)['visual_reviews']), 1)

    def test_unbounded_loop_stops_at_resource_limit(self):
        graph, _, _ = self.graph(*[{'action': 'read_context'} for _ in range(8)])
        self.assertEqual(self.invoke(graph)['agent_status']['state'], 'resource_limit')

    def test_generation_refusal_never_submits_job(self):
        brief = self.brief()
        graph, _, runtime = self.graph(
            {'action': 'plan_generation', 'brief': brief['id'], 'generation': {'title': 'Candidate', 'request': 'Draw a circle.', 'parents': [self.reference]}},
            {'action': 'generate'})
        config = {'configurable': {'thread_id': 'art-test'}}
        with patch('cine_toaster.creation_jobs.image_providers', return_value={'codex-image': lambda: SimpleNamespace(binary='/fake')}), \
             patch.object(runtime, 'start_reference') as start:
            first = self.invoke(graph)
            self.assertTrue(first['__interrupt__'])
            graph.invoke(Command(resume={'approved': False}), config)
            start.assert_not_called()

    def test_quota_consent_does_not_authorise_a_changed_plan(self):
        brief = self.brief()
        graph, _, runtime = self.graph(
            {'action': 'plan_generation', 'brief': brief['id'], 'generation': {'title': 'Candidate', 'request': 'Draw a circle.', 'parents': [self.reference]}},
            {'action': 'generate'})
        with patch('cine_toaster.creation_jobs.image_providers', return_value={'codex-image': lambda: SimpleNamespace(binary='/fake')}), \
             patch.object(runtime, 'start_reference') as start:
            self.assertTrue(self.invoke(graph)['__interrupt__'])
            self.brief(based_on=brief['id'])
            state = graph.invoke(Command(resume={'approved': True}), {'configurable': {'thread_id': 'art-test'}})
            self.assertEqual(state['agent_status']['state'], 'blocked')
            start.assert_not_called()

    def test_ready_human_request_requires_a_successful_pixel_review(self):
        brief = self.brief()
        graph, _, _ = self.graph({'action': 'request_review', 'brief': brief['id']},
                                 {'action': 'respond', 'status': 'needs_review', 'reply': 'Approve this.'})
        self.assertEqual(self.invoke(graph)['agent_status']['state'], 'blocked')
        self.assertEqual(load_creation(self.root).get('assessments', []), [])

    def test_coordinator_delegates_art_without_forcing_inception(self):
        from cine_toaster.project import load_production
        model = Model({'action': 'delegate_art_direction', 'reply': ''},
                      {'action': 'respond', 'status': 'needs_direction', 'reply': 'Which intended mood should this serve?'})
        runtime = Runtime(self.root)
        production = load_production(Path(__file__).parents[1] / 'examples/demo-project') | {'id': 'shapes', 'title': 'Shapes'}
        with patch.object(runtime, 'production', return_value=production):
            state = build(model, runtime).invoke({'messages': [HumanMessage(content='Discuss art direction')], 'ag-ui': {}})
        self.assertEqual(state['active_role'], 'art_direction')
        self.assertIn('Art Direction specialist', model.calls[-1][0])

    def test_generation_reuses_real_job_engine_and_non_overwriting_adoption(self):
        from cine_toaster.jobs import JobManager, JobStore
        brief = self.brief()
        graph, _, runtime = self.graph(
            {'action': 'plan_generation', 'brief': brief['id'], 'generation': {'title': 'Candidate', 'request': 'Draw a circle.', 'parents': [self.reference]}},
            {'action': 'generate'}, {'action': 'respond', 'reply': 'Candidate retained.', 'status': 'complete'})
        runtime.manager = JobManager(store=JobStore(self.root.parent / 'jobs.sqlite'))
        self.addCleanup(runtime.manager.shutdown, wait=True)

        def generate(sandbox, **kwargs):
            return add_reference(sandbox, [self.picture], title=kwargs['title'], kind='generated',
                                 name=kwargs['name'], parents=kwargs['parents'], prompt=kwargs['prompt'],
                                 generation={'made_with': 'synthetic-test-fixture'})

        with patch('cine_toaster.creation_jobs.image_providers', return_value={'codex-image': lambda: SimpleNamespace(binary='/fake')}), \
             patch('cine_toaster.creation_jobs.generate_reference', side_effect=generate):
            first = self.invoke(graph)
            self.assertTrue(first['__interrupt__'])
            state = graph.invoke(Command(resume={'approved': True}), {'configurable': {'thread_id': 'art-test'}})
        job = runtime.manager.get(state['art_job'])
        self.assertEqual(job['state'], 'succeeded', job)
        self.assertTrue(job['adopted_at'])
        self.assertEqual(len(creation_view(self.root)['references']), 2)


class VisualAdapterTests(unittest.TestCase):
    def test_codex_attaches_actual_bytes_in_isolated_request_without_enabling_tools(self):
        from cine_toaster.agents.models import CodexCli
        seen = {}
        def run(command, **kwargs):
            path = Path(command[command.index('--image') + 1]); seen['path'] = path
            self.assertEqual(path.read_bytes(), b'fixture image bytes')
            self.assertIn('view_image', command)  # disabled filesystem tool stays disabled
            Path(command[command.index('--output-last-message') + 1]).write_text('{"reply":"inspected"}')
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        adapter = CodexCli()
        with patch.object(adapter, 'available', return_value=''), patch('cine_toaster.agents.models.subprocess.run', side_effect=run):
            result = adapter.ask_images('review', 'context', {'type': 'object', 'properties': {'reply': {'type': 'string'}}, 'required': ['reply']},
                      [{'mime_type': 'image/png', 'data': base64.b64encode(b'fixture image bytes').decode()}])
        self.assertEqual(result['reply'], 'inspected')
        self.assertFalse(seen['path'].exists())
