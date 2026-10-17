"""Verify Inception readiness and human direction; no model calls or real-film decisions.

Default mode exercises decisions on a disposable production. --inspect ORIGIN
only reads the live production and never clicks approval/rejection controls.
"""
from __future__ import annotations

import argparse
import json
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

from cine_toaster.creation import load_creation, save_creation_draft
from cine_toaster.creation_review import record_inception_assessment
from cine_toaster.jobs import JobManager, JobStore
from cine_toaster.new_production import create_production
from cine_toaster.state import Actor
from cine_toaster.web import ProjectBrowserHandler


def read(origin):
    with urlopen(origin + "/api/creation") as response:
        return json.load(response)


def inspect(origin, evidence):
    before = read(origin)
    current = before["inception_review"]["current"]
    assert current, "A recorded assessment is required"
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(origin + "/app/creation.html")
        region = page.get_by_role("region", name="Inception readiness", exact=True)
        expect(region).to_be_visible(timeout=30000)
        expect(region.get_by_text(current["proposal"]["question"], exact=True)).to_be_visible()
        expect(region.locator(".creation-readiness-destinations > article")).to_have_count(len(current["readiness"]))
        if current["status"] == "awaiting_decision":
            expect(region.get_by_role("button", name="Approve direction", exact=True)).to_be_enabled()
            expect(region.get_by_role("button", name="Request changes", exact=True)).to_be_enabled()
        expect(page.locator("main input, main textarea, main select")).to_have_count(0)
        page.screenshot(path=str(evidence / "01-live-readiness.png"), full_page=True)
        region.get_by_text("2 gaps & next actions", exact=True).first.click()
        page.screenshot(path=str(evidence / "02-live-gaps.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), "Mobile overflow"
        page.screenshot(path=str(evidence / "03-live-mobile.png"), full_page=True)
        assert not errors, errors
        browser.close()
    assert read(origin) == before, "Inspection changed production records"
    print(f"PASS: live readiness, scoped request, gap explanation and mobile; no decisions submitted. Evidence: {evidence}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect")
    args = parser.parse_args()
    evidence = Path(tempfile.mkdtemp(prefix="cine-toaster-inception-review-"))
    if args.inspect:
        inspect(args.inspect.rstrip("/"), evidence)
        return
    with tempfile.TemporaryDirectory(prefix="cine-toaster-inception-film-") as directory:
        base = Path(directory)
        root = base / "film"
        create_production(root, "Inception direction acceptance")
        actor = Actor(id="agent", kind="agent")
        def assess(summary="There is enough material to develop the story."):
            return record_inception_assessment(root, title="Ready to develop", summary=summary,
                readiness=[{"destination": "screenplay", "status": "ready", "summary": "The intention is clear.", "gaps": []},
                           {"destination": "masters", "status": "needs_work", "summary": "Identity needs a later choice.",
                            "gaps": [{"description": "No identity choice.", "owner": "agent", "next_action": "Propose candidates before masters."}]}],
                proposal={"destination": "screenplay", "question": "Develop this direction?", "scope": "Exploratory writing only.",
                          "why": "No finished identity is required to write.", "next_step": "Develop a screenplay candidate."},
                references=[], expected_revision=load_creation(root)["revision"], actor=actor)
        first = assess()["assessment"]
        manager = JobManager(store=JobStore(base / "jobs.sqlite"))
        server = ThreadingHTTPServer(("127.0.0.1", 0), ProjectBrowserHandler)
        server.project_root = root
        server.job_manager = manager
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f"http://127.0.0.1:{server.server_address[1]}"
        errors = []
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1600, "height": 1100})
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(origin + "/app/creation.html")
                expect(page.get_by_text("Awaiting your decision", exact=True)).to_be_visible()
                expect(page.locator("main input, main textarea, main select")).to_have_count(0)
                page.screenshot(path=str(evidence / "01-awaiting-decision.png"), full_page=True)
                page.get_by_role("button", name="Approve direction", exact=True).click()
                expect(page.get_by_text("Direction approved", exact=True)).to_be_visible()
                expect(page.get_by_text("This instruction alone is not proof of execution", exact=False)).to_be_visible()
                page.reload()
                expect(page.get_by_text("Direction approved", exact=True)).to_be_visible()
                self_state = load_creation(root)
                assert self_state["assessment_decisions"][0]["assessment"] == first["id"]
                assert self_state["assessment_decisions"][0]["actor"]["kind"] == "human"
                assess("A second scoped proposal for review.")
                page.get_by_role("button", name="Refresh records", exact=True).click()
                expect(page.get_by_text("Awaiting your decision", exact=True)).to_be_visible()
                page.get_by_role("button", name="Request changes", exact=True).click()
                expect(page.get_by_role("button", name="Send direction", exact=True)).to_be_disabled()
                guidance = "Clarify the emotional turn before developing this direction."
                page.get_by_label("Direction for the next pass", exact=True).fill(guidance)
                # A competing agent commits newer creative material while the human writes.
                save_creation_draft(root, kind="concept", title="New evidence", text="An altered premise.",
                    expected_revision=load_creation(root)["revision"], actor=actor)
                page.get_by_role("button", name="Send direction", exact=True).click()
                expect(page.get_by_role("alert").filter(has_text="Your direction text was retained")).to_be_visible()
                expect(page.get_by_label("Direction for the next pass", exact=True)).to_have_value(guidance)
                page.get_by_role("button", name="Refresh records", exact=True).click()
                expect(page.get_by_text("Material changed · agent to reassess", exact=True)).to_be_visible()
                expect(page.get_by_role("button", name="Approve direction", exact=True)).to_have_count(0)
                assess("New evidence incorporated into this assessment.")
                page.get_by_role("button", name="Refresh records", exact=True).click()
                page.get_by_role("button", name="Request changes", exact=True).click()
                page.get_by_label("Direction for the next pass", exact=True).fill(guidance)
                page.get_by_role("button", name="Send direction", exact=True).click()
                expect(page.get_by_text("Changes requested · agent to reassess", exact=True)).to_be_visible()
                page.reload()
                expect(page.get_by_text("Changes requested · agent to reassess", exact=True)).to_be_visible()
                state = load_creation(root)
                assert len(state["assessments"]) == 3 and len(state["assessment_decisions"]) == 2
                assert state["assessment_decisions"][-1]["guidance"] == guidance
                page.screenshot(path=str(evidence / "02-directed-revision.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), "Mobile overflow"
                page.screenshot(path=str(evidence / "03-mobile.png"), full_page=True)
                assert not errors, errors
                browser.close()
            print(f"PASS: readiness, approve, guided changes, reload, stale/conflicting decision and retained history; no model called. Evidence: {evidence}")
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)
            manager.shutdown(wait=True)


if __name__ == "__main__":
    main()
