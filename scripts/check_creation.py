"""Exercise Creation -> screenplay on a disposable production, never on the director's film.

Uses the real HTTP operations and built GUI. Generation is a deterministic fake,
so this consumes no subscription quota and does not establish provider quality.
Run: .venv/bin/python scripts/check_creation.py
"""
from __future__ import annotations

import base64
import argparse
import json
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

from cine_toaster.creation import load_creation
from cine_toaster.jobs import JobManager, JobStore
from cine_toaster.new_production import create_production
from cine_toaster.references import add_reference, load_references
from cine_toaster.web import ProjectBrowserHandler


def inspect(origin: str):
    """Read-only inspection of real references and assistant context; never submits text."""
    origin = origin.rstrip("/")
    evidence = Path(tempfile.mkdtemp(prefix="cine-toaster-creation-live-"))
    with urlopen(origin + "/api/creation") as response:
        before = json.load(response)
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(origin + "/app/creation.html")
        expect(page.get_by_role("heading", name=before["title"], exact=True)).to_be_visible(timeout=30000)
        expect(page.locator(".creation-gallery > article")).to_have_count(len(before["references"]))
        for picture in page.locator(".creation-gallery > article > a > img").all():
            picture.scroll_into_view_if_needed()
            expect(picture).to_be_visible()
            page.wait_for_function("image => image.complete && image.naturalWidth > 0", arg=picture.element_handle())
        rounds = before.get("active_rounds", before["rounds"])
        if rounds and rounds[-1]["corrections"]:
            pair = rounds[-1]["corrections"][0]
            for ref_id in (pair["previous"], pair["current"]):
                page.locator(f'[id="reference-{ref_id}"]').get_by_role("button", name="Compare", exact=True).click()
            for index, round_ in enumerate(rounds):
                expect(page.get_by_role("heading", name=f"Round {index + 1} · {round_['title']}", exact=True)).to_be_visible()
            expect(page.locator(".creation-history-detail")).not_to_have_attribute("open", "")
            page.locator(".creation-round-gallery").scroll_into_view_if_needed()
            page.screenshot(path=str(evidence / "01-images-by-round.png"))
        else:
            page.get_by_role("button", name="Compare", exact=True).nth(0).click()
            page.get_by_role("button", name="Compare", exact=True).nth(1).click()
        expect(page.get_by_label("Reference comparison").locator("figure")).to_have_count(2)
        page.get_by_label("Reference comparison").scroll_into_view_if_needed()
        page.screenshot(path=str(evidence / "01-real-reference-comparison.png"))
        page.evaluate("window.scrollTo(0, 0)")
        page.screenshot(path=str(evidence / "02-creation-workspace.png"))
        with urlopen(origin + "/api/copilotkit/info") as response:
            assert response.status == 200
        assistant = page.locator('iframe[title="Creative assistant"]').element_handle().content_frame()
        assistant.wait_for_selector('textarea, [contenteditable="true"]', timeout=30000)
        assistant.evaluate("""() => {
          window.creationContexts = [];
          window.addEventListener('message', event => {
            if (event.origin === location.origin && event.data?.type === 'cine-toaster:context')
              window.creationContexts.push(event.data.seen);
          });
        }""")
        expect(page.locator("main input, main textarea, main select")).to_have_count(0)
        page.get_by_role("button", name="Compare", exact=True).first.click()
        assistant.wait_for_function("window.creationContexts.some(context => context.room === 'creation' && JSON.parse(context.details).compared_references.length)")
        page.evaluate("window.scrollTo(0, 0)")
        page.screenshot(path=str(evidence / "03-live-assistant.png"))
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Mobile viewport overflows"
        page.screenshot(path=str(evidence / "04-mobile.png"))
        assert not errors, errors
        browser.close()
    with urlopen(origin + "/api/creation") as response:
        assert json.load(response) == before, "Inspection changed production records"
    print(f"PASS: {len(before['references'])} real reference records and thumbnails, comparison, actual assistant composer/context, mobile overflow; production records unchanged. Evidence: {evidence}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", help="Read-only inspection of a running film; assistant must be enabled")
    args = parser.parse_args()
    if args.inspect:
        inspect(args.inspect)
        return
    # Agents use application operations; the human-facing GUI inspects their results.
    from cine_toaster.creation import save_creation_draft, save_exploration_round
    from cine_toaster.state import Actor
    evidence = Path(tempfile.mkdtemp(prefix="cine-toaster-creation-review-"))
    with tempfile.TemporaryDirectory(prefix="cine-toaster-creation-film-") as directory:
        base = Path(directory)
        root = base / "film"
        create_production(root, "Creation acceptance film")
        picture = base / "reference.png"
        picture.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aZ1sAAAAASUVORK5CYII="))
        first = add_reference(root, [picture], title="Original direction", kind="made", name="original")
        add_reference(root, [picture], title="Alternative direction", kind="made", name="alternative", parents=[first.name])
        actor = Actor(id="production-agent", kind="agent")
        concept = save_creation_draft(root, kind="concept", title="Light as a guide", text="A girl grows through animation eras.",
            expected_revision=0, actor=actor, references=[first.name])["draft"]
        screenplay = save_creation_draft(root, kind="screenplay", title="Screenplay trial", text="Title: Trial\n\nEXT. MEADOW - DAY\n\nShe runs.\n",
            expected_revision=1, actor=actor, concept=concept["id"])["draft"]
        save_exploration_round(root, title="First exploration", references=[first.name], expected_revision=2,
            actor=actor, rationale="Explore the direction.", source="Agent's recorded work")
        original = load_creation(root)
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
                expect(page.get_by_role("heading", name="Creation acceptance film", exact=True)).to_be_visible()
                expect(page.get_by_text("The assistant is off for this session.", exact=True)).to_be_visible()
                expect(page.locator("main input, main textarea, main select")).to_have_count(0)
                expect(page.get_by_role("button", name="Save new version", exact=True)).to_have_count(0)
                page.get_by_role("button", name="Compare", exact=True).nth(0).click()
                page.get_by_role("button", name="Compare", exact=True).nth(1).click()
                expect(page.get_by_label("Reference comparison").locator("figure")).to_have_count(2)
                page.get_by_role("complementary", name="Saved candidates").get_by_role("button").filter(has_text=concept["title"]).click()
                expect(page.get_by_role("region", name="Saved candidate").get_by_role("heading", name=concept["title"], exact=True)).to_be_visible()
                page.reload()
                expect(page.get_by_role("region", name="Saved candidate")).to_contain_text(concept["text"])
                page.get_by_role("complementary", name="Saved candidates").get_by_role("button").filter(has_text=screenplay["title"]).click()
                page.get_by_role("link", name="Review screenplay candidate →", exact=True).click()
                expect(page).to_have_url(origin + "/app/preproduction.html?draft=" + screenplay["id"])
                page.go_back()
                expect(page.get_by_role("region", name="Saved candidate")).to_be_visible()
                page.screenshot(path=str(evidence / "01-situational-inception.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), "Mobile overflow"
                page.screenshot(path=str(evidence / "02-mobile.png"), full_page=True)
                assert not errors, errors
                browser.close()
            assert load_creation(root) == original, "GUI inspection changed agent-produced records"
            print(f"PASS: agent-produced candidates, form-free human inspection, comparison, input handoff, reload/back and preservation. Evidence: {evidence}")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            manager.shutdown(wait=True)


if __name__ == "__main__":
    main()
