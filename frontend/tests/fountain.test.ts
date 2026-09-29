import { test } from "node:test";
import assert from "node:assert/strict";
import { classify, outline, startState } from "../src/fountain.ts";

const kinds = (text: string) => {
  const state = startState();
  return text.split("\n").map((line) => classify(line, state));
};

test("a title page, a heading, action, and a speech", () => {
  const text = "Title: FILM\nAuthor: A\n\nINT. ROOM - DAY\n\nShe waits.\n\nANA\n(quietly)\nYou're late.\n\nCUT TO:";
  assert.deepEqual(kinds(text), [
    "title", "title", "blank", "heading", "blank", "action", "blank",
    "character", "parenthetical", "dialogue", "blank", "transition",
  ]);
});

test("forced elements and extensions", () => {
  const text = ".FLASHBACK\n\n@McCLANE\nYippee.\n\nBRICK (O.S.) ^\nSteel.\n\n!LOUD NOISES.\n\n> FADE OUT\n\n>THE END<";
  assert.deepEqual(kinds(text).filter((kind) => kind !== "blank"), [
    "heading", "character", "dialogue", "character", "dialogue", "action", "transition", "centered",
  ]);
});

test("notes, sections, synopses, boneyard and page breaks", () => {
  const text = "INT. A - DAY\n\n# Act one\n\n= The setup\n\n[[check the light]]\n\n/* cut\nthis */\n\n===";
  assert.deepEqual(kinds(text).filter((kind) => kind !== "blank"), [
    "heading", "section", "synopsis", "note", "boneyard", "boneyard", "pagebreak",
  ]);
});

test("a sentence in capitals ending in punctuation is action, not a cue", () => {
  assert.deepEqual(kinds("INT. A - DAY\n\nBANG!\n\nNothing moves."), ["heading", "blank", "action", "blank", "action"]);
});

test("the outline counts repeated headings across files", () => {
  const seen = new Map<string, number>();
  const first = outline("INT. ROOM - DAY\n\nA.\n\n# Part two\n\nINT. ROOM - DAY #12#\n\nB.", seen);
  const second = outline(".INT. ROOM - DAY\n\nC.", seen);
  assert.deepEqual(first.map((entry) => [entry.kind, entry.line, entry.occurrence]), [
    ["heading", 1, 1], ["section", 5, 0], ["heading", 7, 2],
  ]);
  assert.equal(second[0].occurrence, 3);
});
