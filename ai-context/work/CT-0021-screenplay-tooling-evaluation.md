---
id: CT-0021
title: Evaluate Fountain editing and Final Draft interchange
type: work
status: doing
owner: unassigned
created_at: 2026-09-27
updated_at: 2026-09-29
tags:
  - interface
  - screenplay
  - fountain
  - fdx
---

# What

Evaluate existing screenplay tools for a real writing workflow in Cine Toaster:
Fountain parsing, editing, structured navigation and preview, plus Final Draft
`.fdx` import/export. Choose components only after a focused compatibility spike.

# Why

Cine Toaster currently finds an authored `.fountain` file, reads it as UTF-8,
and displays the raw text in the Script room. It does not parse Fountain
elements, edit a screenplay, paginate it, or import/export FDX. Classifying an
`.fdx` file as a document is not screenplay interchange. A dedicated tool may
cover these functions more reliably than a new parser or editor built here.

# Done

- Audited `project.py`, the Script room, `classify.py`, dependencies, and writing
  tests to establish the current support boundary.
- Reviewed the [Fountain syntax](https://fountain.io/syntax/) and
  [Final Draft's import guidance](https://kb.finaldraft.com/hc/en-us/articles/15575076862228-Can-Final-Draft-import-a-file-written-in-a-Fountain-based-screenwriting-program).
  Final Draft does not directly open `.fountain`; FDX interchange must be tested
  as its own path.
- Shortlisted existing projects for a hands-on spike:

  | Candidate | Potential use | Open question |
  | --- | --- | --- |
  | [Scriptum](https://github.com/argocine/Scriptum) (MIT) | Fountain and FDX import/export, screenplay editor and pagination | Can its core and I/O modules be reused without adopting its Electron app or native `.scriptum` format? |
  | [ScreenplayJS](https://github.com/Guernsey-Creative/screenplay-js) (MIT) | Fountain parsing and structured preview; example FDX-to-Fountain conversion | How complete is conversion and preservation of real FDX files? |
  | [screenplay-tools](https://github.com/wildwinter/screenplay-tools) (MIT) | Fountain parsing/writing in Python and JavaScript | Its documented FDX API is C#; verify which language builds actually include FDX before relying on it. |
  | [CodeMirror](https://codemirror.net/) (MIT) | Browser text-editing foundation | Fountain-specific behavior would still need an integration. |

- **Hands-on test, 2026-09-29.** screenplay-tools was cloned (MIT, pure
  Python, no dependencies, v0.0.10) and run through the project's virtual
  environment. It parsed the demo screenplay and its own dialogue and
  parenthetical samples correctly. Its **Python build includes an FDX parser
  and writer**, which resolves the open question in the table above: a real
  Final Draft file (`TestFDX-FD.fdx`, 16 elements) converted to correct
  Fountain. Elements carry no source positions, so references must be
  text-anchored.
- The user's actual requirement is granular: **each storyboard view must know
  the screenplay and dialogue it holds.** That is specified as
  [`SPEC-0006`](../specs/SPEC-0006-screenplay-coverage.md) (draft).

- **SPEC-0006 implemented (plan step 1).** Scenes link to screenplay
  scenes, shots cover units by quote, and each storyboard frame, the Script
  room, and the Dialogue room read coverage. `toast script show|link` is
  available. screenplay-tools 0.0.10 is a pinned runtime dependency.

- **FDX interchange spike done (plan step 5, 2026-09-29).** Decision:
  [ADR 0014](../../docs/architecture/0014-final-draft-is-interchange.md).
  - Samples: `TestFDX-FD.fdx` (saved by Final Draft) and `TestFDX-FI.fdx`
    (Fade In) from screenplay-tools. A richer case was built from the Final
    Draft file with styled runs, dual dialogue, a Shot, scene number `12A` and
    a revision mark.
  - screenplay-tools' FDX reader and writer lose content silently: a
    paragraph is cut at its first style change, dual dialogue is dropped, a
    Shot becomes a scene heading, and scene numbers, revisions and the title
    page are lost. Its Fountain writer turns "FADE TO BLACK" into action.
  - Implemented `cine_toaster/fdx.py`. Import writes a new Fountain file
    (`toast script import-fdx`, which refuses to overwrite) and reports each
    loss. Export (`toast script export-fdx`) writes a derived `.fdx`. The demo
    screenplay and the richer file round-trip with identical units and title.
  - Anchor normalisation now ignores Fountain emphasis.
  - **Not verified:** opening the export in Final Draft; script notes and
    tags from a real file.

# To do

- Test the candidates with Fountain's examples and representative production
  scripts, including title pages, scenes, dialogue, dual dialogue, notes,
  sections, emphasis, Unicode, and intentional whitespace.
- ~~Round-trip sample FDX files~~ done (ADR 0014). Remaining: open an
  export in Final Draft, and test a real file with script notes, tags and
  revisions.
- Compare screenplay navigation, auto-formatting, keyboard flow, preview,
  performance, browser/Tauri fit, maintenance, dependencies, and license details.
- ~~Define a screenplay write command~~ done in plan step 8 (ADR 0016,
  CT-0036). The original step read: define a screenplay write command with
  revision/conflict handling. Keep the
  authored screenplay in project files; the editor must not write around the
  shared command boundary.
- ~~Decide FDX's role~~ decided: interchange only (ADR 0014).

# Decisions

- **Scheduled on 2026-09-29.** The work is split across the ordered plan in
  `development/roadmap.md`:
  - **step 3:** parse Fountain into structure, read only;
  - **step 5:** FDX interchange spike;
  - **step 8:** screenplay editor in the React stack.
- **An editor conflicts with ADR 0006 as written.** ADR 0006 lists screenplays
  among authored files that are never rewritten, because a serializer
  round-trip destroys comments and notes. The editor therefore edits the
  Fountain **text**, never a parsed model, and saves through a command with a
  revision check. It needs an explicit ADR 0006 amendment before it ships.
  Agents only propose diffs.
- FDX import creates a new authored Fountain file. FDX export is a derived
  artifact. Neither rewrites the source. Recorded as ADR 0014.

- Current Fountain support is read-only display, not full screenplay support.
- Keep the existing project file authoritative. No editor or external document
  format becomes production state by default.
- Prefer evaluating reusable components over embedding an entire second app.
  This is a screening result, not an adoption decision.

# Validation

- Read-only code audit and official/project documentation review. No candidate
  has yet been installed or exercised against Cine Toaster fixtures.
