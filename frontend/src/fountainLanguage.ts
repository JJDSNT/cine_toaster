import { HighlightStyle, StreamLanguage, syntaxHighlighting } from "@codemirror/language";
import { tags as t } from "@lezer/highlight";
import { classify, startState, type LineKind, type LineState } from "./fountain.ts";

// Each line is one token, coloured by its Fountain kind (fountain.ts).
const TOKENS: Record<LineKind, string | null> = {
  title: "meta", heading: "heading", transition: "keyword", centered: "quote",
  character: "strong", parenthetical: "emphasis", dialogue: "string", lyric: "string",
  section: "heading2", synopsis: "comment", note: "comment", boneyard: "comment",
  pagebreak: "contentSeparator", action: null, blank: null,
};

const fountain = StreamLanguage.define<LineState>({
  name: "fountain",
  startState,
  copyState: (state) => ({ ...state }),
  token(stream, state) {
    const kind = classify(stream.string, state);
    stream.skipToEnd();
    return TOKENS[kind];
  },
  blankLine(state) {
    classify("", state);
  },
  tokenTable: {
    heading: t.heading1, heading2: t.heading2, keyword: t.keyword, quote: t.quote, strong: t.strong,
    emphasis: t.emphasis, string: t.string, comment: t.comment, meta: t.meta, contentSeparator: t.contentSeparator,
  },
});

const style = HighlightStyle.define([
  { tag: t.heading1, color: "#ff8a5c", fontWeight: "700" },
  { tag: t.heading2, color: "#b99ae0", fontWeight: "700" },
  { tag: t.keyword, color: "#6fb7d9", fontWeight: "600" },
  { tag: t.quote, color: "#d9c56f" },
  { tag: t.strong, color: "#e7b75c", fontWeight: "700" },
  { tag: t.emphasis, color: "#9aa5ab", fontStyle: "italic" },
  { tag: t.string, color: "#e8ecee" },
  { tag: t.comment, color: "#6f7b80", fontStyle: "italic" },
  { tag: t.meta, color: "#8fcf8a" },
  { tag: t.contentSeparator, color: "#56616a" },
]);

export const fountainSupport = [fountain, syntaxHighlighting(style)];
