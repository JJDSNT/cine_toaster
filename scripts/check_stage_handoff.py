"""Real GUI/CoAgent/HTTP handoff on a disposable film; no production approvals."""
import json
import shutil
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen

from PIL import Image
from playwright.sync_api import expect, sync_playwright

from check_inception_agent import free_ports
from cine_toaster.assistant_host import AssistantHost
from cine_toaster.creation import creation_view, load_creation
from cine_toaster.creation_review import record_inception_assessment
from cine_toaster.jobs import JobManager, JobStore
from cine_toaster.references import add_reference
from cine_toaster.state import Actor
from cine_toaster.storyboard import load_storyboard
from cine_toaster.web import ProjectBrowserHandler

CRITERION = 'The synthetic red fixture is visible; no artistic quality claim.'


class HandoffModel:
    name = 'synthetic-handoff-acceptance-model'

    def __init__(self, root, reference):
        self.root = root; self.reference = reference; self.calls = []

    def ask(self, system, prompt, schema):
        self.calls.append({'system': system, 'prompt': prompt})
        assert 'Art Direction specialist' in system, system
        state = load_creation(self.root)
        assert state['stage_handoffs'][0]['id'] in prompt
        if not state.get('art_briefs'):
            return {'action': 'save_brief', 'reply': '', 'draft': {'title': 'Synthetic storyboard brief',
                'text': 'A synthetic fixture tests handoff and retention, not film quality.',
                'criteria': [CRITERION], 'references': [self.reference]}}
        brief = state['art_briefs'][-1]['id']
        if not load_storyboard(self.root)['candidates']:
            return {'action': 'save_storyboard', 'reply': '', 'board': {'scene': 'SC-010', 'shot': 'P1',
                    'reference': self.reference, 'file': 'fixture.png', 'title': 'Retained synthetic storyboard draft'}}
        if not state.get('visual_reviews'):
            return {'action': 'inspect', 'reply': '', 'brief': brief, 'references': [self.reference]}
        if len(state['assessments']) == 1:
            return {'action': 'request_review', 'reply': '', 'brief': brief}
        return {'action': 'respond', 'reply': 'The retained storyboard candidate and its visual precheck are ready for review.', 'status': 'needs_review'}

    def ask_images(self, system, prompt, schema, images):
        assert 'Visual Prevalidation' in system and images and 'Conversation:' not in prompt
        return {'summary': 'The synthetic red test drawing is visible; this is not an artistic quality judgment.',
                'verdict': 'ready_for_human', 'findings': [{'criterion': CRITERION, 'status': 'pass',
                'evidence': 'The attached fixture is red.', 'correction': 'No correction to this test criterion.'}]}


def main():
    evidence = Path(tempfile.mkdtemp(prefix='cine-toaster-stage-handoff-'))
    with tempfile.TemporaryDirectory(prefix='cine-toaster-handoff-film-') as directory:
        base = Path(directory); root = base / 'film'
        shutil.copytree(Path(__file__).parents[1] / 'examples/demo-project', root)
        Image.new('RGB', (128, 128), 'red').save(base / 'fixture.png')
        reference = add_reference(root, [base / 'fixture.png'], title='Synthetic storyboard fixture', kind='made').name
        record_inception_assessment(root, title='Opening development', summary='Enough to develop the first storyboard shot.',
            references=[reference], readiness=[{'destination': 'storyboard', 'status': 'ready', 'summary': 'Development only', 'gaps': []}],
            proposal={'destination': 'storyboard', 'question': 'Develop the opening storyboard?', 'scope': 'SC-010 / P1 only.',
                      'why': 'Exact fixture scope.', 'next_step': 'Develop a retained storyboard candidate for the opening.'},
            expected_revision=0, actor=Actor(id='inception', kind='agent'))
        manager = JobManager(store=JobStore(base / 'jobs.sqlite'))
        server = ThreadingHTTPServer(('127.0.0.1', 0), ProjectBrowserHandler)
        server.project_root = root; server.job_manager = manager
        origin = f'http://127.0.0.1:{server.server_address[1]}'
        agent, copilot = free_ports(); host = AssistantHost(origin, agent, copilot)
        server.assistant = host; model = HandoffModel(root, reference)
        with patch('cine_toaster.agents.models.model_from_env', return_value=model):
            host.start()
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        errors = []
        try:
            deadline = time.monotonic() + 30
            while True:
                try:
                    with urlopen(origin + '/api/copilotkit/info') as response:
                        assert response.status == 200
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise
                    time.sleep(.1)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={'width': 1440, 'height': 1050})
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(origin + '/app/preproduction.html?scene=SC-010')
                page.get_by_role('link', name='Awaiting you · 1', exact=True).click(timeout=30000)
                expect(page.get_by_role('heading', name='1 pending decision', exact=True)).to_be_visible(timeout=30000)
                expect(page.get_by_text('SC-010 / P1', exact=True)).to_be_visible()
                expect(page.get_by_role('link', name='Open request in context →')).to_have_attribute('href', '/app/creation.html#direction-review')
                page.screenshot(path=str(evidence / '01-pending-with-explicit-target.png'), full_page=True)
                page.get_by_role('button', name='Approve & advance', exact=True).click()
                # This starts the existing CoAgent; no manually typed second message.
                expect(page.get_by_role('heading', name='Review these retained storyboard candidates?', exact=True)).to_be_visible(timeout=120000)
                assistant = page.frame_locator('iframe[title="Creative assistant"]')
                expect(assistant.get_by_test_id('assistant-role')).to_contain_text('Art Direction · Awaiting your review', timeout=30000)
                expect(page.get_by_role('button', name='Approve & advance', exact=True)).to_have_count(0)
                expect(page.get_by_role('button', name='Approve direction', exact=True)).to_be_visible()
                expect(page.get_by_role('link', name='Storyboard SC-010 / P1', exact=True)).to_be_visible()
                page.screenshot(path=str(evidence / '02-approved-input-to-retained-output.png'), full_page=True)
                state = load_creation(root); board = load_storyboard(root)['candidates'][0]
                assert len(state['assessment_decisions']) == len(state['stage_handoffs']) == 1
                assert len(state['assessments']) == 2 and board['provenance']['handoff'] == state['stage_handoffs'][0]['id']
                assert not creation_view(root)['handoffs'][0]['stale']
                page.get_by_role('link', name='Storyboard SC-010 / P1', exact=True).click()
                expect(page.locator('.prep-drawing')).to_contain_text('Retained synthetic storyboard draft', timeout=30000)
                page.reload()
                expect(page.locator('.prep-drawing')).to_contain_text('Retained synthetic storyboard draft', timeout=30000)
                page.set_viewport_size({'width': 390, 'height': 844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), 'Mobile overflow'
                page.screenshot(path=str(evidence / '03-output-reload-mobile.png'), full_page=True)
                page.goto(origin + '/app/decisions.html')
                expect(page.get_by_role('heading', name='1 pending decision', exact=True)).to_be_visible(timeout=30000)
                page.route('**/api/decisions', lambda route: route.fulfill(status=503, content_type='application/json', body='{"error":{"message":"Offline fixture"}}'))
                page.get_by_role('button', name='Refresh decisions').click()
                expect(page.get_by_role('alert')).to_contain_text('Could not refresh decisions')
                assert not errors, errors
                browser.close()
            (evidence / 'model-calls.json').write_text(json.dumps(model.calls, indent=2))
            print(f'PASS: global inbox -> explicit human approval -> same CoAgent Art Direction -> real retained storyboard -> visual precheck -> new gate; reload/mobile/error. Evidence: {evidence}')
        finally:
            host.stop(); server.shutdown(); server.server_close(); thread.join(timeout=5); manager.shutdown(wait=True)


if __name__ == '__main__':
    main()
