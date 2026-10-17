import { strict as assert } from "node:assert";
import { describe, it } from "node:test";
import { drawingPreview, drawingVersions, type StoryDrawing, type StoryDrawings } from "../src/storyboard.ts";

describe("storyboard draft navigation", () => {
  const first = { id: "one", scene: "SC-010", shot: "P1", version: 1 } as StoryDrawing;
  const second = { ...first, id: "two", version: 2 };
  const other = { ...first, id: "other", shot: "P2" };
  const data = { candidates: [first, second, other], revision: 3, coverage: [] } as StoryDrawings;
  it("previews the latest without dropping older versions or mixing shots", () => {
    const versions = drawingVersions(data, "SC-010", "P1");
    assert.deepEqual(versions.map((item) => item.id), ["two", "one"]);
    assert.equal(drawingPreview(versions, ""), second);
    assert.equal(drawingPreview(versions, "one"), first);
    assert.equal(data.candidates[0], first);
  });
  it("does not silently substitute another drawing for a broken explicit link", () => {
    assert.equal(drawingPreview(drawingVersions(data, "SC-010", "P1"), "other"), undefined);
    assert.deepEqual(drawingVersions(null, "SC-010", "P1"), []);
  });
});
