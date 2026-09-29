// Fountain, line by line: enough to colour a screenplay while it is written
// and to list its scenes. It is not the parser -- the runtime's screenplay
// model (screenplay-tools) decides what the film's scenes and lines are.

export type LineKind =
  | "title" | "heading" | "transition" | "centered" | "character" | "parenthetical"
  | "dialogue" | "lyric" | "section" | "synopsis" | "note" | "boneyard" | "pagebreak"
  | "action" | "blank";

export interface LineState {
  /** Still in the title page (the document's first block of `Key: value` lines). */
  titlePage: boolean;
  previousBlank: boolean;
  inDialogue: boolean;
  inBoneyard: boolean;
}

export const startState = (): LineState => ({ titlePage: true, previousBlank: true, inDialogue: false, inBoneyard: false });

const HEADING = /^(INT|EXT|EST|INT\.?\/EXT|I\/E)[.\s]/i;
const TITLE_KEY = /^[A-Za-z][A-Za-z ]*:/;

export function isHeading(line: string): boolean {
  const text = line.trim();
  return (text.startsWith(".") && !text.startsWith("..")) || HEADING.test(text);
}

/** The kind of one line, given what came before it. Updates `state`. */
export function classify(line: string, state: LineState): LineKind {
  const text = line.trim();
  if (state.inBoneyard) {
    if (text.includes("*/")) state.inBoneyard = false;
    return "boneyard";
  }
  if (!text) {
    state.previousBlank = true;
    state.inDialogue = false;
    if (state.titlePage) state.titlePage = false;
    return "blank";
  }
  const after = (kind: LineKind): LineKind => {
    state.previousBlank = false;
    return kind;
  };
  if (state.titlePage) {
    if (TITLE_KEY.test(text) || /^\s/.test(line)) return after("title");
    state.titlePage = false;
  }
  if (text.startsWith("/*")) {
    if (!text.includes("*/")) state.inBoneyard = true;
    return after("boneyard");
  }
  if (text === "===" || /^={3,}$/.test(text)) return after("pagebreak");
  if (text.startsWith("[[") && text.endsWith("]]")) return after("note");
  if (text.startsWith("#")) return after("section");
  if (text.startsWith("=")) return after("synopsis");
  if (state.inDialogue) {
    if (text.startsWith("(") && text.endsWith(")")) return after("parenthetical");
    if (text.startsWith("~")) return after("lyric");
    return after("dialogue");
  }
  if (text.startsWith(">") && text.endsWith("<")) return after("centered");
  if (text.startsWith(">")) return after("transition");
  if (text.startsWith("!")) return after("action");
  if (isHeading(text)) return after("heading");
  if (text === text.toUpperCase() && text.endsWith("TO:")) return after("transition");
  if (text.startsWith("~")) return after("lyric");
  const name = text.replace(/\s*\^$/, "").replace(/\s*\([^)]*\)\s*$/, "");
  const cue = text.startsWith("@") || (/[A-Z]/.test(name) && name === name.toUpperCase() && !/[.!?]$/.test(name));
  if (state.previousBlank && cue) {
    state.inDialogue = true;
    return after("character");
  }
  return after("action");
}

export interface OutlineEntry {
  line: number;
  kind: "heading" | "section";
  text: string;
  /** How many times this heading appeared before it, counted from the first file. */
  occurrence: number;
}

export function normalizeHeading(text: string): string {
  return text.replace(/#[^#]*#\s*$/, "").replace(/^\./, "").replace(/\s+/g, " ").trim().toUpperCase();
}

/** Scenes and sections of one file, with occurrences continuing from `seen`. */
export function outline(text: string, seen: Map<string, number> = new Map()): OutlineEntry[] {
  const state = startState();
  const entries: OutlineEntry[] = [];
  text.split(/\r?\n/).forEach((line, index) => {
    const kind = classify(line, state);
    if (kind === "heading") {
      const key = normalizeHeading(line);
      const occurrence = (seen.get(key) ?? 0) + 1;
      seen.set(key, occurrence);
      entries.push({ line: index + 1, kind, text: line.trim().replace(/^\./, ""), occurrence });
    } else if (kind === "section") {
      entries.push({ line: index + 1, kind, text: line.trim().replace(/^#+\s*/, ""), occurrence: 0 });
    }
  });
  return entries;
}
