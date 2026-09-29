# ADR 0014: Final Draft is interchange, never the screenplay of record

Status: accepted

## Context

Writers work in Final Draft, and producers receive `.fdx` files. Cine Toaster
reads its screenplay as Fountain (SPEC-0006). Shots anchor to that
screenplay's text, and ADR 0006 keeps it authored and never rewritten. Plan
step 5 tested what an `.fdx` can carry into that model and back (`CT-0021`).

The FDX support in screenplay-tools, the Fountain parser Cine Toaster depends
on, was measured against a file saved by Final Draft and a richer version of
it. Its losses are **silent**:

- a paragraph is cut off at its first style change: "We are in **a TV
  station** listening…" arrives as "We are in";
- dual dialogue disappears;
- a Shot becomes a scene heading. That creates a scene the film does not
  have, and shifts every scene link counted by occurrence;
- scene numbers, revision marks and the title page are dropped, and its
  Fountain writer turns a transition such as "FADE TO BLACK" into action.

A real file also stores much that Fountain cannot hold: revision sets, script
notes, production tags, scene properties, locked pages, alternate lines,
outlines and element formatting.

## Decision

FDX is an **interchange format**, and its two directions are asymmetric:

- **Import** (`toast script import-fdx`) writes a **new** Fountain file and
  never overwrites an existing one. That file becomes the authored screenplay.
  Every element that cannot be kept is counted and reported at import, never
  dropped silently.
- **Export** (`toast script export-fdx`) writes a **derived** `.fdx` from the
  authored Fountain. It is never edited as the screenplay and never read back
  as truth. Changes made in Final Draft return through a new import.

Both directions are implemented in `cine_toaster/fdx.py` with the standard
library. screenplay-tools still parses the Fountain side.

**Supported subset**, round-tripped without loss at unit level:

| Kept both ways | Fountain side |
| --- | --- |
| Scene heading with scene number (`12A`) | `INT. … #12A#`, forced `.` when needed |
| Action, General | action, forced `!` when it would read as something else |
| Character with extension, Parenthetical, Dialogue | speech |
| Dual dialogue | `^` on the second cue |
| Transition | plain when it ends in `TO:`, otherwise forced `>` |
| Bold, italic, underline runs | `**`, `*`, `_` |
| Page break (`StartsNewPage`) | `===` |
| Title page | `Title`, `Credit`, `Author`, `Copyright`, `Contact` |

Reported as lost on import: revision marks and their sets, script notes, tags,
scene properties, Shot as an element type (written as forced action), other
element types, locked pages, alternate lines, images, outlines, and text
styles beyond the three above.

Reported as lost on export: Fountain notes, sections, synopses and the
boneyard. Element formatting and page layout are left to Final Draft's
defaults.

Final Draft's title page is laid out rather than labelled, so it is read by
position: centred lines give the title, then the credit and the authors, and
left-aligned lines are contact details. The import report says so.

## Consequences

- A writer's revision colours and notes do not survive the move into Cine
  Toaster. A production that needs them keeps the `.fdx` as a source document
  beside the screenplay.
- Production tags from Final Draft are not imported. Cast, locations and props
  are records in Cine Toaster (ADR 0012), and tag import would need its own
  mapping.
- Anchors ignore emphasis, so a shot's `covers` quoted in plain text still
  finds a line that arrived in bold.
- **Not verified in Final Draft itself.** The exported file follows the
  structure of a file Final Draft saved, but it has not been opened in Final
  Draft. Script notes and tags were not tested against a real file. Test both
  when a real production file is available.
