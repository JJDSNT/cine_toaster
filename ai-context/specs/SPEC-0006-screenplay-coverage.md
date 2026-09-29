---
id: SPEC-0006
title: Screenplay coverage — every shot knows the screenplay and dialogue it holds
type: specification
status: implemented
implementation: complete
owner: project
created_at: 2026-09-29
updated_at: 2026-09-29
tags:
  - project-core
  - screenplay
  - fountain
  - dialogue
  - storyboard
---

# Goal

Every view of a shot shows exactly which part of the screenplay that shot
covers: the storyboard card, the scene room, the brief, and later the canvas
node. That means its action lines, and its dialogue with speaker,
parenthetical, and dual-dialogue marks. The screenplay says it once, and every
view reads it from there. A line nobody films, and a filmed line that no longer
matches the screenplay, are both visible before anything is generated.

# Context

Today the screenplay and the shots are disconnected:

- `writing_room` reads the `.fountain` file as raw text for the Script room.
- Spoken words live a second time in each shot's authored `lines`, typed
  again, with no link to the screenplay.
- The storyboard card shows the shot's label and nothing from the screenplay.

When the screenplay is rewritten, nothing tells the breakdown. A production
can therefore generate a shot whose dialogue is a draft behind.

The CT-0021 screening named the candidate tools. The hands-on test on
2026-09-29 settled the parser: **screenplay-tools** (MIT, pure Python, no
dependencies, `wildwinter/screenplay-tools`). Its Python build:

- parses Fountain into typed elements (heading, action, character with
  extension and dual flag, parenthetical, dialogue, transition, and more);
- **includes an FDX parser and writer**, which the screening had left in doubt.
  A real Final Draft file (`TestFDX-FD.fdx`, 16 elements) converted to correct
  Fountain.

Elements carry no source positions, so references are anchored by text, as
SceneFlow anchors its cues (CT-0022).

# Model

## A scene names its screenplay scene

```yaml
scene: SC-030
script:
  heading: INT. LISTENING STATION - NIGHT
  occurrence: 2          # only when the same heading appears more than once
```

Headings are matched after normalization: case, whitespace, and a trailing
scene number. Without `script`, a scene is simply not linked, which is the
current behaviour.

## A shot names the part it covers

```yaml
shots:
  - n: 3
    covers:
      from: "The speaker stack repeats"     # the start of an element's text
      to: "MARA: I never sent that."        # CHARACTER: marks a dialogue anchor
```

- An **anchor** is the start of an element's text, matched after
  normalization. A `CHARACTER:` prefix restricts the match to that
  character's dialogue.
- `from` and `to` are inclusive, in screenplay order, within the linked scene.
  `to` defaults to `from`, which covers one element.
- `covers` may be a list of ranges, for a shot that skips lines.
- Coverage may overlap. A master shot and its close-ups cover the same lines,
  and that is coverage in the film sense, not an error.
- An anchor that matches more than one element is an error that names the
  candidates. The author lengthens the anchor.

## What a shot derives

From its covered range, each shot exposes:

- `script.elements`: the covered elements in order, as type, text, and
  character with extension;
- `script.dialogue`: speaker, parenthetical, text, `dual`, and extension
  (V.O., O.S.);
- `script.action`: action text.

These are derived and read-only. The screenplay stays the single source of the
words.

## Authored `lines` become metadata

A shot's `lines` keep what the screenplay does not hold: `delivery`, `voice`,
`mix`, and translations. Each authored line is matched to a covered dialogue
element by speaker and text. The screenplay's text is canonical. An authored
`text` that differs is reported, never silently preferred.

## Adopting it in an existing production

`toast script link <project>` **proposes** coverage for productions that
already have authored `lines`. Each line is matched to screenplay dialogue by
speaker and normalized text, and the command prints `covers` suggestions with
confidence. It never writes the authored breakdown (ADR 0006). The author
pastes the suggestions, or an agent proposes them as a decision.

# Checks

| Code | Severity | Meaning |
| --- | --- | --- |
| `script_scene_missing` | error | A scene's `script.heading` matches no screenplay scene. |
| `script_anchor_missing` | error | A `covers` anchor matches nothing in the linked scene. |
| `script_anchor_ambiguous` | error | An anchor matches more than one element; the candidates are listed. |
| `dialogue_uncovered` | warning | A dialogue element in a linked scene is covered by no shot. It is a line nobody films. |
| `line_drift` | warning | A shot's authored line differs from the screenplay text it matches. Either the breakdown or the screenplay is out of date. |
| `line_unscripted` | advice | A shot's authored line matches no covered dialogue. It may be a deliberate ad-lib, so this is advice, not an error. |

Each check gets a recorded practice (ADR 0009).

# Views

- **Storyboard.** Each card shows its covered dialogue (speaker and line) and a
  one-line action excerpt beneath the frame. A card whose shot covers nothing
  says so.
- **Script room.** The screenplay is rendered formatted rather than as raw
  text. Each element carries the ids of the shots that cover it, in the margin.
  Uncovered dialogue is highlighted. Clicking a shot id opens the shot.
- **Dialogue room.** Lines come from coverage. Authored metadata such as voice
  and delivery is attached where it matches.
- **Brief builder** (plan step 4). `[AUDIO]` and dialogue come from coverage.

# Dependency

`screenplay-tools` becomes a runtime dependency, pinned to an exact version,
beside `pyyaml`. The justification follows the existing `pyproject.toml`
convention: the screenplay is a core contract, and the library is small, pure
Python, and MIT. It is early (0.0.10), so it stays behind one module
(`screenplay.py`), and every call to it goes through that module. Replacing or
vendoring it later changes one file.

# Compatibility

- Every field is optional. An unlinked scene behaves as today.
- The authored `.fountain` file and breakdown are only read (ADR 0006).
- The demo production gains dialogue in its screenplay and `covers` on
  SC-030, so the feature is exercised by a built-in example.

# Acceptance

- Fountain is parsed through `screenplay.py`, tested with the Fountain spec
  samples and the demo screenplay.
- Scene linking and anchors work, with tests for normalization, occurrence,
  ambiguity, and lists of ranges.
- Per-shot `script` is derived and exposed through the scene and writing
  queries.
- Every check in the table passes and fails in a test.
- `toast script link` proposes coverage from authored lines.
- The storyboard cards, the Script room margin, and the Dialogue room read
  coverage. The demo shows it. Visual behaviour is verified with a headless
  screenshot.
- `toast check` still passes on both demos.

# Implementation notes

- The code is in `src/cine_toaster/screenplay.py`, the only importer of
  screenplay-tools, with linking in `project.py` (`_link_screenplay`) and
  `toast script show|link` in `cli.py`.
- **Action paragraphs are split by us.** The parser merges consecutive
  action paragraphs into one element, and its unmerged mode splits line by
  line. A shot boundary usually falls between paragraphs, so each
  blank-line-separated paragraph becomes a unit. The demo exposed this.
- A speech is one unit: character, parentheticals, and dialogue. Its text
  reads as one line, and its parts keep line breaks and parentheticals.
- Drift is judged by `difflib` similarity (≥ 0.6) to the speaker's covered
  speeches. Containment failed on a changed final full stop.
- The demo screenplay gained dialogue. SC-010 and SC-030 share a heading, so
  SC-030 uses `occurrence: 2`.
- Validated with 20 tests in `tests/test_screenplay.py`, `toast script
  show|link` on the demo and on a de-linked copy, and headless screenshots of
  the storyboard cards and the Script room coverage, including an uncovered
  line.

# Relation to SceneFlow

- **Same anchoring principle.** Both link to the script by text: exact match,
  then whitespace- and quote-normalized, then case-insensitive. SPEC-0006
  anchors whole elements; SceneFlow cues anchor any substring.
- **Complementary questions.** Coverage says which elements a shot *should*
  hold, at planning time. SceneFlow's Timeline Anatomy says *when* each
  fragment happens in a take, at review time. Timing is the natural next layer
  over coverage, and coverage narrows each take's alignment search to that
  shot's lines.
- **Cue types map onto existing records:**
  - dialogue and action come from coverage;
  - camera and shot come from SPEC-0005;
  - transition comes from the cut record;
  - `[OPENING]` is the blocking frame (CT-0025).
- **Tension 1: source of truth.** SceneFlow's hand-written Auteur Script is
  both screenplay and prompt. Here the brief is derived from records. It can
  be exported in Auteur Script form, and in SceneFlow's project JSON so its
  Timeline Anatomy can review Cine Toaster takes. Whether a shot may carry a
  hand-written execution override is open. If allowed, it is an explicit
  field that visibly replaces the derived brief.
- **Tension 2: one generation, several shots.** Vector Field generates about 8
  `[CAM]` setups per clip; here a take belongs to one shot. Multi-setup
  generation would need a generation unit spanning shots, with cut points
  inside the take. Cue timing is exactly that data. This must be decided
  before the first generation adapter (plan step 9). It does not affect this
  specification.

# Open questions

- Whether FDX import (plan step 5) should preserve Final Draft scene numbers
  as the `occurrence`-free identity of a heading.
- Line timing inside a take, SceneFlow's Timeline Anatomy, is out of scope.
  Coverage says *which* lines a shot holds, not *when* each is spoken.
