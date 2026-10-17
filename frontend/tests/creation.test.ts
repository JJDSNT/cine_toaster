import { strict as assert } from "node:assert";
import { test } from "node:test";
import { candidateAddress, conceptOf, referenceGroups, request, type CreationState, type Draft } from "../src/creation.ts";
import { addressOf } from "../src/navigation.ts";

test("candidate review links preserve the exact identity rather than selecting the current film script", () => {
  assert.equal(candidateAddress("draft_a #1"), "/app/preproduction.html?draft=draft_a%20%231");
});
test("handoff reads a declared concept input, not an inferred predecessor", () => {
  const draft = { based_on: "previous-screenplay", inputs: [
    { kind: "reference", id: "ref", sha256: "one" }, { kind: "concept", id: "saved-concept", sha256: "two" },
  ] } as Draft;
  assert.equal(conceptOf(draft), "saved-concept");
  assert.equal(conceptOf({ ...draft, inputs: [] }), "");
});
test("assistant navigation can reach the actual Creation entry", () => {
  assert.equal(addressOf({ room: "creation", scene: "", shot: "", id: "" }), "/app/creation.html");
});
test("image groups follow arbitrary project rounds, not fixed demo categories", () => {
  const data = { references: [{ id: "a", title: "First" }, { id: "b", title: "Second" }, { id: "c", title: "New image" }],
    active_rounds: [{ id: "r1", title: "Costume", references: [{ id: "a" }] },
      { id: "r2", title: "Lighting", references: [{ id: "b" }] }], rounds: [],
  } as unknown as CreationState;
  const groups = referenceGroups(data);
  assert.deepEqual(groups.map((group) => [group.number, group.title, group.references.map((ref) => ref.id)]),
    [[1, "Costume", ["a"]], [2, "Lighting", ["b"]], [null, "Unassigned references", ["c"]]]);
});
test("failed saves expose the server's conflict instead of returning an apparent saved version", async () => {
  const previous = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ error: { code: "revision_conflict", message: "A newer version exists" } }), { status: 409 });
  try { await assert.rejects(request("/api/creation", { expected_revision: 0 }), /A newer version exists/); }
  finally { globalThis.fetch = previous; }
});
