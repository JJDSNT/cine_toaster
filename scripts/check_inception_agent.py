"""Browser acceptance of the real CoAgents graph with deterministic model answers.

Uses a disposable film and the existing HTTP, LangGraph, supervised Copilot
sidecar and GUI. No real model call, image generation or Demo 01 mutation.
"""
from __future__ import annotations

import json
import socket
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

from cine_toaster.assistant_host import AssistantHost
from cine_toaster.creation import load_creation
from cine_toaster.jobs import JobManager, JobStore
from cine_toaster.new_production import create_production
from cine_toaster.web import ProjectBrowserHandler


class AcceptanceModel:
    name = "deterministic-acceptance-model"

    def __init__(self, root):
        self.root = root
        self.calls = []

    def ask(self, system, prompt, schema):
        self.calls.append({"system": system, "prompt": prompt})
        assert "Inception specialist" in system
        state = load_creation(self.root)
        drafts = state["drafts"]
        decisions = state.get("assessment_decisions", [])
        assessments = state.get("assessments", [])
        if not drafts or decisions and len(drafts) == 1:
            return {"action": "save_concept", "reply": "", "draft": {
                "title": "Quiet discovery" if drafts else "First discovery",
                "text": "The child notices a quiet trace of light." if drafts else "A child discovers a trail of light.",
                "based_on": drafts[0]["id"] if drafts else "", "references": []}}
        if len(assessments) < len(drafts):
            return {"action": "assess_readiness", "reply": "", "assessment": {
                "title": "Opening readiness", "summary": "Enough material to develop the opening screenplay.",
                "readiness": [{"destination": "screenplay", "status": "ready", "summary": "A saved concept is available.", "gaps": []}],
                "proposal": {"destination": "screenplay", "question": "Develop the quieter opening?" if decisions else "Develop this opening?",
                    "scope": "Opening screenplay only; no image generation.", "why": "The dramatic intention is clear.",
                    "next_step": "Prepare a screenplay candidate from the saved concept."}, "references": []}}
        return {"action": "respond", "reply": "A new retained version and its readiness assessment are ready for your review.",
                "status": "needs_review"}


def free_ports():
    with socket.socket() as first, socket.socket() as second:
        first.bind(("127.0.0.1", 0)); second.bind(("127.0.0.1", 0))
        return first.getsockname()[1], second.getsockname()[1]


def main():
    evidence = Path(tempfile.mkdtemp(prefix="cine-toaster-inception-agent-"))
    with tempfile.TemporaryDirectory(prefix="cine-toaster-agent-film-") as directory:
        base = Path(directory)
        root = base / "film"
        create_production(root, "Agent loop acceptance")
        original_script = (root / "story/screenplay.fountain").read_bytes()
        manager = JobManager(store=JobStore(base / "jobs.sqlite"))
        server = ThreadingHTTPServer(("127.0.0.1", 0), ProjectBrowserHandler)
        server.project_root = root
        server.job_manager = manager
        origin = f"http://127.0.0.1:{server.server_address[1]}"
        agent_port, copilot_port = free_ports()
        host = AssistantHost(origin, agent_port, copilot_port)
        server.assistant = host
        model = AcceptanceModel(root)
        with patch("cine_toaster.agents.models.model_from_env", return_value=model):
            host.start()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        errors = []
        try:
            deadline = time.monotonic() + 30
            while True:
                try:
                    with urlopen(origin + "/api/copilotkit/info") as response:
                        if response.status == 200:
                            break
                except OSError:
                    if time.monotonic() > deadline:
                        raise
                    time.sleep(.1)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1600, "height": 1100})
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(origin + "/app/creation.html")
                assistant = page.frame_locator('iframe[title="Creative assistant"]')
                composer = assistant.locator("textarea").last
                expect(composer).to_be_visible(timeout=30000)
                composer.fill("Develop a concept for an opening and assess if it is ready for screenplay work.")
                composer.press("Enter")
                expect(page.get_by_text("Awaiting your decision", exact=True)).to_be_visible(timeout=30000)
                expect(assistant.get_by_test_id("assistant-role")).to_contain_text("Inception · Awaiting your review", timeout=30000)
                expect(page.get_by_role("complementary", name="Saved candidates")).to_contain_text("First discovery")
                page.screenshot(path=str(evidence / "01-agent-authored-review.png"), full_page=True)
                page.get_by_role("button", name="Request changes", exact=True).click()
                page.get_by_label("Direction for the next pass", exact=True).fill("Make the discovery quieter.")
                page.get_by_role("button", name="Send direction", exact=True).click()
                # No second chat message / Continue click: canonical human decision triggers the same CoAgent.
                expect(page.get_by_role("complementary", name="Saved candidates")).to_contain_text("Quiet discovery", timeout=30000)
                expect(page.get_by_role("heading", name="Develop the quieter opening?", exact=True)).to_be_visible(timeout=30000)
                expect(assistant.get_by_test_id("assistant-role")).to_contain_text("Awaiting your review", timeout=30000)
                expect(page.locator("main input, main textarea, main select")).to_have_count(0)
                state = load_creation(root)
                assert len(state["drafts"]) == 2 and len(state["assessments"]) == 2, state
                assert state["drafts"][1]["based_on"] == state["drafts"][0]["id"]
                assert state["assessment_decisions"][0]["actor"]["kind"] == "human"
                assert state["drafts"][0]["actor"] == {"id": "inception", "kind": "agent"}
                assert any("Make the discovery quieter" in item["prompt"] for item in model.calls)
                assert (root / "story/screenplay.fountain").read_bytes() == original_script
                page.screenshot(path=str(evidence / "02-guided-retained-revision.png"), full_page=True)
                page.reload()
                expect(page.get_by_role("heading", name="Develop the quieter opening?", exact=True)).to_be_visible(timeout=30000)
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), "Mobile overflow"
                page.screenshot(path=str(evidence / "03-reloaded-mobile.png"), full_page=True)
                assert not errors, errors
                browser.close()
            (evidence / "model-calls.json").write_text(json.dumps(model.calls, indent=2))
            print(f"PASS: actual CoAgent -> Inception tools -> retained review -> human direction -> automatic CoAgent revision; no real model call. Evidence: {evidence}")
        finally:
            host.stop()
            server.shutdown(); server.server_close(); thread.join(timeout=5)
            manager.shutdown(wait=True)


if __name__ == "__main__":
    main()
