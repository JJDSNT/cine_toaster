---
id: CT-0021
title: Evaluate Fountain editing and Final Draft interchange
type: work
status: ready
owner: unassigned
created_at: 2026-09-27
updated_at: 2026-09-27
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

# To do

- Test the candidates with Fountain's examples and representative production
  scripts, including title pages, scenes, dialogue, dual dialogue, notes,
  sections, emphasis, Unicode, and intentional whitespace.
- Round-trip sample FDX files through import, editing, and export. Record lost
  content and metadata, page-layout differences, and unsupported features.
- Compare screenplay navigation, auto-formatting, keyboard flow, preview,
  performance, browser/Tauri fit, maintenance, dependencies, and license details.
- Define a screenplay write command with revision/conflict handling. Keep the
  authored screenplay in project files; the editor must not write around the
  shared command boundary.
- Decide whether FDX is an interchange format or warrants another role. Record
  the chosen component and supported subset before claiming full support.

# Decisions

- Current Fountain support is read-only display, not full screenplay support.
- Keep the existing project file authoritative. No editor or external document
  format becomes production state by default.
- Prefer evaluating reusable components over embedding an entire second app.
  This is a screening result, not an adoption decision.

# Validation

- Read-only code audit and official/project documentation review. No candidate
  has yet been installed or exercised against Cine Toaster fixtures.
