"""Browser vertical slice: real CoAgent, HTTP operations and raster attachments.

Uses a synthetic fixture/model on a disposable film; no paid generation or
production-film decisions. Evidence is retained outside the production.
"""
from __future__ import annotations

import json
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen

from PIL import Image, ImageDraw
from playwright.sync_api import expect, sync_playwright

from check_inception_agent import free_ports
from cine_toaster.assistant_host import AssistantHost
from cine_toaster.creation import load_creation
from cine_toaster.jobs import JobManager, JobStore
from cine_toaster.new_production import create_production
from cine_toaster.references import add_reference
from cine_toaster.web import ProjectBrowserHandler

CRITERION = 'A red circle is legible against the dark background.'


class ArtModel:
    name = 'synthetic-art-acceptance-model'

    def __init__(self, root, reference):
        self.root = root; self.reference = reference; self.calls = []; self.visual_calls = 0

    def ask(self, system, prompt, schema):
        self.calls.append({'system': system, 'prompt': prompt})
        if 'Inception specialist' in system:
            return {'action': 'delegate_art_direction', 'reply': ''}
        assert 'Art Direction specialist' in system
        state = load_creation(self.root)
        if not state.get('art_briefs'):
            return {'action': 'save_brief', 'draft': {'title': 'Red circle visual identity',
                'text': 'Use a restrained dark field and a clear red circular motif.',
                'references': [self.reference], 'criteria': [CRITERION]}}
        brief = state['art_briefs'][-1]['id']
        if not state.get('visual_reviews'):
            return {'action': 'inspect', 'brief': brief, 'references': [self.reference]}
        if not state.get('assessments'):
            return {'action': 'request_review', 'brief': brief}
        return {'action': 'respond', 'status': 'needs_review', 'reply': 'The visual brief and independent precheck are ready for your review.'}

    def ask_images(self, system, prompt, schema, images):
        import base64
        self.visual_calls += 1
        assert 'Visual Prevalidation' in system and 'Conversation:' not in prompt
        assert len(images) == 1 and base64.b64decode(images[0]['data']).startswith(b'\x89PNG')
        return {'summary': 'The red motif is visible with clear contrast.', 'verdict': 'ready_for_human',
                'findings': [{'criterion': CRITERION, 'status': 'pass',
                              'evidence': 'The red disc is centered on a near-black field.',
                              'correction': 'No correction needed for this criterion.'}]}


def main():
    evidence = Path(tempfile.mkdtemp(prefix='cine-toaster-art-agents-'))
    with tempfile.TemporaryDirectory(prefix='cine-toaster-art-film-') as directory:
        base = Path(directory); root = create_production(base / 'film', 'Art agent acceptance').root
        image = Image.new('RGB', (256, 256), '#101014')
        ImageDraw.Draw(image).ellipse((72, 72, 184, 184), fill='#ed3030')
        image.save(base / 'fixture.png')
        reference = add_reference(root, [base / 'fixture.png'], title='Synthetic motif fixture', kind='made').name
        manager = JobManager(store=JobStore(base / 'jobs.sqlite'))
        server = ThreadingHTTPServer(('127.0.0.1', 0), ProjectBrowserHandler)
        server.project_root = root; server.job_manager = manager
        origin = f'http://127.0.0.1:{server.server_address[1]}'
        agent, copilot = free_ports(); host = AssistantHost(origin, agent, copilot)
        server.assistant = host; model = ArtModel(root, reference)
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
                page = browser.new_page(viewport={'width': 1500, 'height': 1000})
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(origin + '/app/creation.html')
                assistant = page.frame_locator('iframe[title="Creative assistant"]')
                composer = assistant.locator('textarea').last
                expect(composer).to_be_visible(timeout=30000)
                composer.fill('Develop the art direction and independently inspect this visual candidate.')
                composer.press('Enter')
                panel = page.get_by_role('region', name='Art direction and visual prevalidation')
                expect(panel.get_by_role('heading', name='Ready for human creative review')).to_be_visible(timeout=30000)
                expect(page.get_by_text('Awaiting your decision', exact=True)).to_be_visible(timeout=30000)
                expect(assistant.get_by_test_id('assistant-role')).to_contain_text('Art Direction · Awaiting your review', timeout=30000)
                expect(panel).to_contain_text('The red disc is centered')
                expect(page.locator('main input, main textarea, main select')).to_have_count(0)
                page.screenshot(path=str(evidence / '01-art-and-independent-review.png'), full_page=True)
                page.reload()
                expect(page.get_by_role('region', name='Art direction and visual prevalidation')).to_contain_text('The red disc is centered')
                page.set_viewport_size({'width': 390, 'height': 844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), 'Mobile overflow'
                page.screenshot(path=str(evidence / '02-retained-mobile.png'), full_page=True)
                state = load_creation(root)
                assert len(state['art_briefs']) == len(state['visual_reviews']) == len(state['assessments']) == 1
                assert state.get('assessment_decisions', []) == [] and model.visual_calls == 1
                assert not errors, errors
                (evidence / 'records.json').write_text(json.dumps(state, indent=2))
                (evidence / 'model-calls.json').write_text(json.dumps(model.calls, indent=2))
                browser.close()
            print(f'PASS: real CoAgent -> Art Direction -> image attachments -> independent review -> human gate; reload/mobile. Evidence: {evidence}')
        finally:
            host.stop(); server.shutdown(); server.server_close(); thread.join(timeout=5)
            manager.shutdown(wait=True)


if __name__ == '__main__':
    main()
