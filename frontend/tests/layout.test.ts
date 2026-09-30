import { test } from "node:test";
import assert from "node:assert/strict";
import { layout, SIZES } from "../src/layout.ts";
import type { GraphNode } from "../src/types.ts";

const scene = (id: string, order: number): GraphNode => ({
  id: `scene:${id}`, type: "scene", scene: id,
  data: { scene: id, title: id, order, revision: 0, location: "", plates: [], sequence: "", status: "", findings: 0, severity: "" },
});
const shot = (sceneId: string, id: string, order: number): GraphNode => ({
  id: `shot:${sceneId}/${id}`, type: "shot", scene: sceneId,
  data: {
    scene: sceneId, shot: id, order, label: "", camera: "", duration_seconds: 1, status: "", source: "",
    selected_take: "", takes: 0, speakers: [], move: "", walks: false, picture: { level: "none" }, block: "",
    findings: 0, severity: "", number: id.replace(/^P/, ""), from: [], derived: false, with: [],
    reference_decided: false, authored_from: [], authored_with: [],
  },
});
const take = (sceneId: string, shotId: string, id: string): GraphNode => ({
  id: `take:${sceneId}/${shotId}/${id}`, type: "take", scene: sceneId,
  data: { scene: sceneId, shot: shotId, take: id, label: id, status: "", selected: false, media: "", poster: "" },
});

test("shots run left to right in shot order, whatever order they arrive in", () => {
  const nodes = [scene("A", 0), shot("A", "P2", 1), shot("A", "P1", 0)];
  const at = layout(nodes);
  assert.ok(at.get("shot:A/P1")!.x < at.get("shot:A/P2")!.x);
  assert.equal(at.get("shot:A/P1")!.y, at.get("scene:A")!.y);
});

test("scenes are rows in production order, and takes push the next row down", () => {
  const nodes = [scene("B", 1), scene("A", 0), shot("A", "P1", 0), take("A", "P1", "T1"), take("A", "P1", "T2"), shot("B", "P1", 0)];
  const at = layout(nodes);
  assert.equal(at.get("scene:A")!.y, 0);
  const lastTake = at.get("take:A/P1/T2")!;
  assert.ok(at.get("scene:B")!.y > lastTake.y + SIZES.take.height);
  assert.ok(at.get("take:A/P1/T1")!.y > at.get("shot:A/P1")!.y + SIZES.shot.height);
});

test("hiding takes places no take and tightens the rows", () => {
  const nodes = [scene("A", 0), shot("A", "P1", 0), take("A", "P1", "T1"), scene("B", 1)];
  assert.equal(layout(nodes, { takes: false }).has("take:A/P1/T1"), false);
  assert.ok(layout(nodes, { takes: false }).get("scene:B")!.y < layout(nodes).get("scene:B")!.y);
});

test("the same graph always lays out the same way", () => {
  const nodes = [scene("A", 0), shot("A", "P1", 0), take("A", "P1", "T1")];
  assert.deepEqual([...layout(nodes)], [...layout(structuredClone(nodes))]);
});

test("a long scene wraps onto further lines instead of one endless row", () => {
  const nodes = [scene("A", 0), ...Array.from({ length: 10 }, (_, i) => shot("A", `P${i + 1}`, i)), scene("B", 1)];
  const at = layout(nodes, { perRow: 4 });
  assert.equal(at.get("shot:A/P5")!.x, at.get("shot:A/P1")!.x);
  assert.ok(at.get("shot:A/P5")!.y > at.get("shot:A/P1")!.y);
  assert.ok(at.get("shot:A/P9")!.y > at.get("shot:A/P5")!.y);
  assert.ok(at.get("scene:B")!.y > at.get("shot:A/P9")!.y + SIZES.shot.height);
});

const run = (sceneId: string, id: string): GraphNode => ({
  id: `run:${sceneId}/${id}`, type: "run", scene: sceneId,
  data: { scene: sceneId, run: id, block: "1", shot: "", state: "waiting", steps: [], waiting: "Approve picture mA" },
});

test("a workflow run sits under its scene's header, and pushes the next scene down", () => {
  const without = layout([scene("A", 0), shot("A", "P1", 0), scene("B", 1)]);
  const nodes = [scene("A", 0), shot("A", "P1", 0), run("A", "wf1"), run("A", "wf2"), scene("B", 1)];
  const at = layout(nodes);
  assert.equal(at.get("run:A/wf1")!.x, 0);
  assert.ok(at.get("run:A/wf1")!.y > at.get("scene:A")!.y + SIZES.header.height - 1);
  assert.ok(at.get("run:A/wf2")!.y > at.get("run:A/wf1")!.y + SIZES.run.height - 1);
  assert.ok(at.get("scene:B")!.y > without.get("scene:B")!.y);
  assert.ok(at.get("scene:B")!.y > at.get("run:A/wf2")!.y + SIZES.run.height);
});
