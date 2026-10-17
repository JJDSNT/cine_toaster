"""Read-only browser walkthrough of the pre-production pilot against a running film.

Run with the repository environment (Playwright and Chromium required):
  .venv/bin/python scripts/check_preproduction.py http://127.0.0.1:8765

No film is edited and no model is called. Screenshots are review evidence,
not proof that visual candidate authoring or human review is implemented.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origin")
    parser.add_argument("--output", type=Path, default=Path("/tmp/cine-toaster-preproduction-review"))
    args = parser.parse_args()
    origin = args.origin.rstrip("/")
    with urlopen(f"{origin}/api/writing") as response:
        writing = json.load(response)
    scenes = [scene for scene in writing["scenes"] if scene["frames"]]
    if len(scenes) < 2:
        raise SystemExit("This walkthrough needs two scenes with proposed shots.")
    first, second = scenes[:2]
    first_shot = first["frames"][0]["shot_id"]
    args.output.mkdir(parents=True, exist_ok=True)
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1050})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(f"{origin}/app/preproduction.html?scene={first['id']}&shot={first_shot}")
        expect(page.get_by_role("heading", name=writing["title"], exact=True)).to_be_visible()
        expect(page.get_by_role("region", name="Screenplay", exact=True)).to_be_visible()
        expect(page.get_by_role("region", name="Storyboard", exact=True)).to_be_visible()
        expect(page.get_by_text("Approval state not loaded", exact=True)).to_have_count(0)
        page.screenshot(path=str(args.output / "01-screenplay-storyboard.png"), full_page=True)

        # Text and shot selection refer to the same production identity.
        passage = page.locator(".prep-unit-links button").first
        passage_shot = passage.inner_text()
        passage.click()
        expect(page.get_by_role("navigation", name="Proposed shots").get_by_role("button", name=f"{passage_shot} ")).to_have_attribute("aria-pressed", "true")
        page.get_by_role("button", name="Composition study", exact=True).click()
        expect(page).to_have_url(f"{origin}/app/preproduction.html?scene={first['id']}&shot={passage_shot}&study=1")
        expect(page.get_by_role("status").filter(has_text="Loading studies")).to_have_count(0)
        page.screenshot(path=str(args.output / "02-composition-study.png"), full_page=True)
        page.reload()
        expect(page.get_by_role("button", name="Composition study", exact=True)).to_have_attribute("aria-pressed", "true")
        expect(page.locator(".prep-unit.selected").first).to_be_visible()

        page.get_by_role("complementary", name="Scenes").get_by_role("button").filter(has_text=second["id"]).click()
        expect(page.get_by_role("heading", name=f"{second['frames'][0]['shot_id']} · {second['frames'][0]['label']}", exact=True)).to_be_visible()
        page.get_by_role("button", name="Composition study", exact=True).click()
        page.wait_for_function("!document.querySelector('.prep-board [role=status]')")
        with urlopen(f"{origin}/api/boards?scene={second['id']}") as response:
            second_boards = json.load(response)
        if not second_boards["shots"][second["frames"][0]["shot_id"]]["boards"]:
            expect(page.get_by_text("No composition study for this shot", exact=True)).to_be_visible()
        page.screenshot(path=str(args.output / "03-second-scene.png"), full_page=True)
        page.go_back()
        expect(page.get_by_role("button", name="Shot visual", exact=True)).to_have_attribute("aria-pressed", "true")

        # When the real service is enabled, open its actual chat and verify the
        # selected film context is delivered, without sending a model message.
        if page.get_by_role("button", name="Assistant · available", exact=True).count():
            page.get_by_role("button", name="Assistant · available", exact=True).click()
            assistant = page.locator('iframe[title="Directing assistant"]').element_handle().content_frame()
            assistant.wait_for_selector('textarea, [contenteditable="true"]', timeout=30000)
            assistant.evaluate("""() => {
                window.reviewContexts = [];
                window.addEventListener('message', event => {
                    if (event.origin === location.origin && event.data?.type === 'cine-toaster:context')
                        window.reviewContexts.push(event.data.seen);
                });
            }""")
            page.get_by_role("button", name="Composition study", exact=True).click()
            assistant.wait_for_function("window.reviewContexts.some(context => context.scene && context.selected && typeof context.details === 'string')")
            page.screenshot(path=str(args.output / "06-live-assistant.png"), full_page=True)
            page.get_by_role("button", name="Close", exact=True).click()

        # Exercise off-state UX without starting a model or changing server state.
        page.route("**/api/copilotkit/info", lambda route: route.fulfill(
            status=503, content_type="application/json",
            body=json.dumps({"error": {"code": "assistant_off"}})))
        page.reload()
        page.get_by_role("button", name="Assistant · off", exact=True).click()
        expect(page.get_by_text("The assistant is off for this server session.", exact=True)).to_be_visible()
        page.screenshot(path=str(args.output / "04-assistant-off.png"), full_page=True)
        page.get_by_role("button", name="Close", exact=True).click()

        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(args.output / "05-mobile.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Page overflows mobile viewport"
        # Verify a service failure is not misreported as a deliberately disabled assistant.
        page.route("**/api/copilotkit/info", lambda route: route.fulfill(
            status=502, content_type="application/json", body='{"error":{"code":"upstream_failure"}}'))
        page.reload()
        page.get_by_role("button", name="Assistant · unavailable", exact=True).click()
        expect(page.get_by_text("The assistant service could not be reached.", exact=True)).to_be_visible()
        assert not errors, errors
        browser.close()
    print(f"PASS: live screenplay/shot navigation, composition view, reload/back, second scene, assistant availability/failure feedback and mobile overflow. Evidence: {args.output}")


if __name__ == "__main__":
    main()
