import { strict as assert } from "node:assert";
import { test } from "node:test";
import { focusSearch, mediaAddress, resolveFocus } from "../src/preproduction.ts";

const scenes = [
  { id: "SC-010", frames: [{ shot_id: "P1" }, { shot_id: "P2" }] },
  { id: "SC-020", frames: [] },
];
test("review deep links survive refresh and preserve study selection", () => {
  const focus = { scene: "SC-010", shot: "P2", study: true };
  assert.deepEqual(resolveFocus(scenes, focusSearch(focus)), focus);
});
test("unknown or empty scene and shot links recover without inventing a shot", () => {
  assert.deepEqual(resolveFocus(scenes, "?scene=missing&shot=P9"), { scene: "SC-010", shot: "P1", study: false });
  assert.deepEqual(resolveFocus(scenes, "?scene=SC-020&shot=P2"), { scene: "SC-020", shot: "", study: false });
  assert.deepEqual(resolveFocus([], "?scene=SC-020"), { scene: "", shot: "", study: false });
});
test("media path segments remain literal instead of becoming URL query or fragment", () => {
  assert.equal(mediaAddress("renders/a #1/p?.png"), "/media/renders/a%20%231/p%3F.png");
});
