"""Disposable-film acceptance: actual public CoAgent, HTTP writes and human handoff."""
from __future__ import annotations

import json
import shutil
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

from check_inception_agent import free_ports
from cine_toaster.assistant_host import AssistantHost
from cine_toaster.creation import load_creation
from cine_toaster.jobs import JobManager, JobStore
from cine_toaster.web import ProjectBrowserHandler


class DirectingModel:
    name = 'synthetic-directing-acceptance-model'

    def __init__(self, root):
        self.root = root; self.calls = []; self.review_calls = 0

    def ask(self, system, prompt, schema):
        self.calls.append({'system': system, 'prompt': prompt})
        if 'Production Coordinator inside' in system:
            return {'action': 'delegate_directing', 'reply': '', 'scene': 'SC-010'}
        if 'independent Script Supervisor' in system:
            assert 'Conversation:' not in prompt and 'Receipts:' not in prompt
            context = json.loads(prompt)
            assert context['continuity']['scenes'] and context['plan']['scene'] == 'SC-010'
            self.review_calls += 1
            return {'summary': 'Coverage and proposed state joins are coherent in this textual scope.',
                    'verdict': 'ready_for_human', 'findings': [], 'limitations': ['No image or numeric camera inspection.']}
        assert 'Directing / Shot Planning' in system
        state = load_creation(self.root); plans = state.get('direction_plans', [])
        changes = state.get('assessment_decisions', [])
        if not plans or (changes and len(plans) == 1):
            if changes:
                assert 'Hold the discovery longer' in prompt
            return {'action': 'save_plan', 'reply': '', 'draft': {
                'scene': 'SC-010', 'title': 'Listening before the reveal' + (' · second pass' if changes else ''),
                'intention': 'Preserve a gradual reveal; hold longer.' if changes else 'Preserve a gradual reveal.',
                'based_on': plans[-1]['id'] if plans else '', 'shots': [{
                    'id': 'A', 'label': 'The listening operator', 'action': 'The operator listens before answering.',
                    'framing': 'Medium close-up', 'camera_intent': 'A restrained hold on the established axis.',
                    'duration_seconds': 12 if changes else 8, 'script_units': [1, 2, 3, 4], 'state_in': [], 'state_out': []}]}}
        plan = plans[-1]['id']
        if not any(item['plan'] == plan for item in state.get('continuity_reviews', [])):
            return {'action': 'review_continuity', 'reply': '', 'plan': plan}
        if not any(item.get('proposal', {}).get('direction_plan') == plan for item in state.get('assessments', [])):
            return {'action': 'request_review', 'reply': '', 'plan': plan, 'review_request': {
                'question': 'Keep this restrained reveal?', 'scope': 'SC-010 proposal only; no storyboard approval.',
                'why': 'Coverage and joins were independently reviewed.', 'next_step': 'Develop the proposal without canonical promotion.'}}
        return {'action': 'respond', 'status': 'needs_review', 'reply': 'The shot proposal and independent continuity report are ready for review.'}


def main():
    evidence = Path(tempfile.mkdtemp(prefix='cine-toaster-directing-agents-'))
    with tempfile.TemporaryDirectory(prefix='cine-toaster-directing-film-') as directory:
        base = Path(directory); root = base / 'film'
        shutil.copytree(Path(__file__).parents[1] / 'examples/demo-project', root)
        manager = JobManager(store=JobStore(base / 'jobs.sqlite'))
        server = ThreadingHTTPServer(('127.0.0.1', 0), ProjectBrowserHandler)
        server.project_root = root; server.job_manager = manager
        origin = f'http://127.0.0.1:{server.server_address[1]}'
        agent, copilot = free_ports(); host = AssistantHost(origin, agent, copilot)
        server.assistant = host; model = DirectingModel(root)
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
                page.goto(origin + '/app/preproduction.html?scene=SC-010')
                page.get_by_role('button', name='Assistant · available').click(timeout=30000)
                assistant = page.frame_locator('iframe[title="Directing assistant"]')
                composer = assistant.locator('textarea').last
                expect(composer).to_be_visible(timeout=30000)
                composer.fill('Develop the shot proposal and independently review continuity.')
                composer.press('Enter')
                panel = page.get_by_role('region', name='Directing and continuity')
                expect(panel.get_by_text('Listening before the reveal · 1 shots · Proposal, not canonical', exact=True)).to_be_visible(timeout=30000)
                expect(panel).to_contain_text('Coverage and proposed state joins are coherent', timeout=30000)
                expect(page.get_by_text('Awaiting your decision', exact=True)).to_be_visible(timeout=30000)
                expect(assistant.get_by_test_id('assistant-role')).to_contain_text('Directing / Shot Planning · Awaiting your review', timeout=30000)
                expect(page.locator('main input, main textarea, main select')).to_have_count(0)
                page.screenshot(path=str(evidence / '01-proposal-and-independent-review.png'), full_page=True)
                page.get_by_role('button', name='Request changes', exact=True).click()
                page.get_by_label('Direction for the next pass').fill('Hold the discovery longer')
                page.get_by_role('button', name='Send direction', exact=True).click()
                expect(panel.get_by_text('Listening before the reveal · second pass · 1 shots · Proposal, not canonical', exact=True)).to_be_visible(timeout=30000)
                expect(page.get_by_text('Awaiting your decision', exact=True)).to_be_visible(timeout=30000)
                expect(panel).to_contain_text('Sources changed / superseded')
                page.screenshot(path=str(evidence / '02-human-direction-retained-revision.png'), full_page=True)
                page.reload()
                expect(panel).to_contain_text('second pass')
                page.set_viewport_size({'width': 390, 'height': 844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), 'Mobile overflow'
                page.screenshot(path=str(evidence / '03-retained-mobile.png'), full_page=True)
                state = load_creation(root)
                assert len(state['direction_plans']) == len(state['continuity_reviews']) == len(state['assessments']) == 2
                assert len(state['assessment_decisions']) == 1 and model.review_calls == 2
                assert not errors, errors
                (evidence / 'records.json').write_text(json.dumps(state, indent=2))
                (evidence / 'model-calls.json').write_text(json.dumps(model.calls, indent=2))
                browser.close()
            print(f'PASS: existing Coordinator -> Directing -> independent Continuity -> human direction -> retained revision; reload/mobile. Evidence: {evidence}')
        finally:
            host.stop(); server.shutdown(); server.server_close(); thread.join(timeout=5)
            manager.shutdown(wait=True)


if __name__ == '__main__':
    main()
