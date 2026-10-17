"""Read-only storyboard/input walkthrough, or a disposable version-navigation check.

    .venv/bin/python scripts/check_storyboard.py --inspect http://127.0.0.1:8787
    .venv/bin/python scripts/check_storyboard.py

No model calls; the real-film mode never writes production records.
"""
from __future__ import annotations

import argparse
import base64
import json
import shutil
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

from cine_toaster.jobs import JobManager, JobStore
from cine_toaster.references import add_reference
from cine_toaster.state import Actor
from cine_toaster.storyboard import register_storyboard_candidate
from cine_toaster.web import ProjectBrowserHandler


def read(origin, path):
    with urlopen(origin + path) as response:
        return json.load(response)


def inspect(origin, evidence, *, versions=False):
    before = read(origin, "/api/storyboard")
    creation = read(origin, "/api/creation")
    first = before["candidates"][0]
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1560, "height": 1100})
        page.on("pageerror", lambda error: errors.append(str(error)))
        address = f"{origin}/app/preproduction.html?scene={first['scene']}&shot={first['shot']}"
        page.goto(address)
        expect(page.get_by_role("img", name=f"{first['shot']} storyboard draft", exact=True)).to_be_visible()
        page.wait_for_function("Array.from(document.querySelectorAll('.prep-drawing img')).every(i => i.complete && i.naturalWidth > 0)")
        expect(page.get_by_text("Preview, not a selected master", exact=False)).to_be_visible()
        expect(page.get_by_role("region", name="Screenplay", exact=True)).to_be_visible()
        page.screenshot(path=str(evidence / "01-storyboard-drawing.png"), full_page=True)
        if versions:
            page.get_by_text("Versions & origin · 2 retained", exact=True).click()
            page.get_by_role("button", name="v1 · First drawing", exact=True).click()
            expect(page).to_have_url(address + f"&candidate={first['id']}")
            page.reload()
            expect(page.get_by_text("Storyboard draft · v1", exact=False)).to_be_visible()
            page.get_by_text("Versions & origin · 2 retained", exact=True).click()
            page.get_by_role("button", name="v2 · Second drawing", exact=True).click()
            expect(page.get_by_text("Storyboard draft · v2", exact=False)).to_be_visible()
            page.go_back()
            expect(page.get_by_text("Storyboard draft · v1", exact=False)).to_be_visible()
            page.get_by_role("button", name="Composition study", exact=True).click()
            expect(page).to_have_url(address + f"&study=1&candidate={first['id']}")
            page.get_by_role("button", name="Shot visual", exact=True).click()
            expect(page.get_by_text("Storyboard draft · v1", exact=False)).to_be_visible()
        # Follow the actual pinned input to its Inception card, then the known use back.
        source = first["inputs"][0]
        page.locator(".prep-drawing").get_by_role("link").first.click()
        card = page.locator(f'[id="reference-{source["id"]}"]')
        expect(card).to_be_visible()
        expect(page.get_by_label("Candidate title", exact=True)).to_have_count(0)
        expect(page.get_by_label("Reference title", exact=True)).to_have_count(0)
        card.get_by_text("Details & history", exact=True).click()
        card.get_by_role("link", name=first["title"], exact=True).click()
        expect(page).to_have_url(address + f"&candidate={first['id']}")
        expect(page.get_by_role("img", name=f"{first['shot']} storyboard draft", exact=True)).to_be_visible()
        if not versions:
            for shot in ("P1", "P2", "P3"):
                page.get_by_role("navigation", name="Proposed shots").get_by_role("button").filter(has_text=shot).click()
                expect(page.get_by_role("img", name=f"{shot} storyboard draft", exact=True)).to_be_visible()
        page.get_by_role("button", name="Composition study", exact=True).click()
        page.wait_for_function("!document.querySelector('.prep-board [role=status]')")
        expect(page.locator(".prep-drawing")).to_have_count(0)
        page.screenshot(path=str(evidence / "02-separate-3d-study.png"), full_page=True)
        page.get_by_role("button", name="Shot visual", exact=True).click()
        other = next(item for item in before["coverage"] if item["shots"] and item["with_candidates"] == 0)
        page.get_by_role("complementary", name="Scenes").get_by_role("button").filter(has_text=other["scene"]).click()
        expect(page.get_by_text("No storyboard drawing for this shot", exact=True)).to_be_visible()
        page.goto(address + "&candidate=not-a-version")
        expect(page.get_by_text("Requested drawing version not found for this shot", exact=True)).to_be_visible()
        page.get_by_role("button", name="Return to latest preview", exact=True).click()
        expect(page.get_by_role("img", name=f"{first['shot']} storyboard draft", exact=True)).to_be_visible()
        page.route("**/api/storyboard", lambda route: route.fulfill(status=500, content_type="application/json", body="{}"))
        page.reload()
        expect(page.get_by_role("alert").filter(has_text="Could not read storyboard candidates")).to_be_visible()
        expect(page.get_by_text("No storyboard drawing for this shot", exact=True)).to_have_count(0)
        page.unroute("**/api/storyboard")
        page.set_viewport_size({"width": 390, "height": 844})
        page.reload()
        expect(page.get_by_role("img", name=f"{first['shot']} storyboard draft", exact=True)).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), "Horizontal overflow"
        page.screenshot(path=str(evidence / "03-mobile.png"), full_page=True)
        if not versions:
            page.set_viewport_size({"width": 1560, "height": 1100})
            page.goto(origin + "/?view=storyboard")
            expect(page.get_by_role("heading", name="Every frame, in order", exact=True)).to_be_visible()
            expect(page.locator('.filmstrip-card img[alt$="storyboard draft"]')).to_have_count(len(before["candidates"]))
            expect(page.locator("#storyboard-nav-count")).to_have_text(str(len(before["candidates"])))
            expect(page.get_by_text("No frames have been drawn yet", exact=True)).to_have_count(0)
            page.screenshot(path=str(evidence / "04-normal-storyboard-entry.png"), full_page=True)
            page.get_by_role("link", name="Review beside screenplay →", exact=True).first.click()
            expect(page.get_by_role("img", name=f"{first['shot']} storyboard draft", exact=True)).to_be_visible()
        assert not errors, errors
        browser.close()
    assert read(origin, "/api/storyboard") == before, "Storyboard records changed during inspection"
    assert read(origin, "/api/creation") == creation, "Creation records changed during inspection"
    print(f"PASS: drawings, separate composition view, input/use trace, missing/error states, mobile and preservation; versions={versions}. Evidence: {evidence}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect")
    args = parser.parse_args()
    evidence = Path(tempfile.mkdtemp(prefix="cine-toaster-storyboard-review-"))
    if args.inspect:
        inspect(args.inspect.rstrip("/"), evidence)
        return
    with tempfile.TemporaryDirectory(prefix="cine-toaster-storyboard-film-") as directory:
        base = Path(directory)
        root = base / "film"
        shutil.copytree(Path(__file__).resolve().parents[1] / "examples/demo-project", root)
        image = base / "drawing.png"
        image.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aZ1sAAAAASUVORK5CYII="))
        reference = add_reference(root, [image], title="Opening concept", kind="made", name="opening")
        saved = register_storyboard_candidate(root, scene="SC-010", shot="P1", image=image, title="First drawing",
            actor=Actor(id="test"), expected_revision=0, references=[reference.name])
        register_storyboard_candidate(root, scene="SC-010", shot="P1", image=image, title="Second drawing",
            actor=Actor(id="test"), expected_revision=1, references=[reference.name], based_on=saved["candidate"]["id"])
        manager = JobManager(store=JobStore(base / "jobs.sqlite"))
        server = ThreadingHTTPServer(("127.0.0.1", 0), ProjectBrowserHandler)
        server.project_root = root
        server.job_manager = manager
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            inspect(f"http://127.0.0.1:{server.server_address[1]}", evidence, versions=True)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)
            manager.shutdown(wait=True)


if __name__ == "__main__":
    main()
