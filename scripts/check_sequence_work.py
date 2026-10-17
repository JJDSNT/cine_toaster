"""Real GUI/CoAgent/HTTP acceptance of explicit AI work on a disposable film."""
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
from cine_toaster.agents.runtime_client import RuntimeClient
from cine_toaster.creation import load_creation
from cine_toaster.jobs import JobManager, JobStore
from cine_toaster.state import Actor
from cine_toaster.storyboard import register_storyboard_candidate
from cine_toaster.web import ProjectBrowserHandler


class Model:
    name = 'deterministic-sequence-work-acceptance'

    def __init__(self, identity):
        self.identity = identity
        self.calls = []

    def ask(self, system, prompt, schema):
        self.calls.append({'system': system, 'prompt': prompt})
        assert 'Production Coordinator' in system
        assert self.identity in prompt and 'sequence_review_capability_missing' in prompt
        assert 'SC-010' in prompt and 'SC-030' in prompt and 'not_dispatched' in prompt
        return {'action': 'none', 'reply': 'The sequence validation remains pending with the Production Coordinator. '
                'The full sequence validator is not implemented; the task is not awaiting your approval and no background run is claimed.'}


def main():
    expect.set_options(timeout=120000)
    evidence = Path(tempfile.mkdtemp(prefix='cine-toaster-sequence-work-'))
    with tempfile.TemporaryDirectory(prefix='cine-toaster-sequence-work-film-') as folder:
        base = Path(folder); root = base / 'film'
        shutil.copytree(Path(__file__).parents[1] / 'examples/demo-project', root)
        image = base / 'fixture.png'; Image.new('RGB', (64, 64), 'red').save(image)
        register_storyboard_candidate(root, scene='SC-010', shot='P1', image=image,
            title='Synthetic retained drawing', expected_revision=0, actor=Actor(id='fixture', kind='agent'))
        manager = JobManager(store=JobStore(base / 'jobs.sqlite'))
        server = ThreadingHTTPServer(('127.0.0.1', 0), ProjectBrowserHandler)
        server.project_root = root; server.job_manager = manager
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        origin = f'http://127.0.0.1:{server.server_port}'
        client = RuntimeClient(origin)
        current = client._call('/api/sequence-work')
        result = client._call('/api/creation/sequence-review-request', {
            'sequence': 'the-reply', 'title': 'Validate Inception against The Reply storyboard',
            'rationale': 'Synthetic authorised fixture request; not a real film review.',
            'expected_revision': current['revision'], 'expected_source_digest': current['source_digest']})
        identity = result['request']['id']; model = Model(identity)
        agent_port, copilot_port = free_ports()
        host = AssistantHost(origin, agent_port, copilot_port); server.assistant = host
        errors = []
        try:
            with patch('cine_toaster.agents.models.model_from_env', return_value=model):
                host.start()
            deadline = time.monotonic() + 30
            while True:
                try:
                    with urlopen(origin + '/api/copilotkit/info') as response:
                        if response.status == 200:
                            break
                except OSError:
                    if time.monotonic() > deadline:
                        raise
                    time.sleep(.1)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={'width': 1440, 'height': 1050})
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(origin + '/app/creation.html')
                page.get_by_role('link', name='AI work · 1', exact=True).click()
                region = page.get_by_role('region', name='AI work', exact=True)
                expect(region.get_by_role('heading', name='Validate Inception against The Reply storyboard')).to_be_visible()
                expect(region).to_contain_text('The Reply · 2 scenes · 5 shots')
                expect(region).to_contain_text('SC-010 → SC-030')
                expect(region).to_contain_text('1/5 shots have drawing records')
                expect(region).to_contain_text('Not dispatched')
                expect(region.get_by_role('button', name='Approve', exact=False)).to_have_count(0)
                expect(page.get_by_role('heading', name='0 pending decisions', exact=True)).to_be_visible()
                page.screenshot(path=str(evidence / '01-explicit-agent-owned-work.png'), full_page=True)
                region.get_by_role('button', name='Discuss this work with the copilot').click()
                assistant = page.frame_locator('iframe[title="Creative assistant"]')
                composer = assistant.locator('textarea').last
                expect(composer).to_be_visible()
                composer.fill('What is pending for this sequence?'); composer.press('Enter')
                expect(assistant.get_by_text('The sequence validation remains pending with the Production Coordinator.', exact=False)).to_be_visible()
                assert model.calls
                page.screenshot(path=str(evidence / '02-coagent-sees-canonical-pending-work.png'), full_page=True)
                page.reload()
                expect(region.get_by_role('heading', name='Validate Inception against The Reply storyboard')).to_be_visible()
                page.set_viewport_size({'width': 390, 'height': 844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), 'Mobile overflow'
                page.screenshot(path=str(evidence / '03-reloaded-mobile.png'), full_page=True)
                page.route('**/api/decisions', lambda route: route.fulfill(status=503, content_type='application/json', body='{}'))
                page.get_by_role('button', name='Refresh decisions').click()
                expect(page.get_by_role('alert')).to_contain_text('Could not refresh decisions')
                expect(region.get_by_role('heading', name='Validate Inception against The Reply storyboard')).to_be_visible()
                assert not errors, errors
                browser.close()
            state = load_creation(root)
            assert state['revision'] == 1 and len(state['sequence_review_requests']) == 1
            assert not state.get('assessment_decisions') and not manager.list()
            (evidence / 'model-calls.json').write_text(json.dumps(model.calls, indent=2))
            print(f'PASS: HTTP request -> GUI AI work -> actual CoAgent sees canonical task/gaps; reload/mobile/error; no generation/approval. Evidence: {evidence}')
        finally:
            host.stop(); server.shutdown(); server.server_close(); thread.join(5); manager.shutdown(wait=True)


if __name__ == '__main__':
    main()
