import test from "node:test";
import assert from "node:assert/strict";
import { workScope, workState, type AgentWork } from "../src/productionWork.ts";

test("sequence scope remains whole even when drawing coverage is partial", () => {
  const work: AgentWork = { id: "work", sequence: "ascent", sequence_label: "The Ascent", scene_ids: ["SC-010", "SC-020"],
    state: "pending_agent", instruction: "Compare original intention", url: "/", coverage: { shots: 8, shots_with_records: 3, meaning: "Records, not approval" } };
  assert.equal(workScope(work), "The Ascent · 2 scenes · 8 shots");
  assert.equal(workState(work), "Pending AI work");
  assert.deepEqual(work.scene_ids, ["SC-010", "SC-020"]);
});

test("removed canonical sequence is not presented as the old current scope", () => {
  assert.equal(workScope({ id: "work", sequence: "gone", scene_ids: ["old"], current_scene_ids: [], state: "pending_agent", instruction: "", url: "" }), "gone · 0 scenes");
});
