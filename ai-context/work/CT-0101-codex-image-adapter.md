---
id: CT-0101
title: The codex-image adapter -- pictures from Codex, kept as references with their lineage
type: work
status: done
owner: claude-code
created_at: 2026-10-16
updated_at: 2026-10-16
tags:
  - providers
  - generation
  - references
  - mcp
---

# What

A provider adapter for Codex's built-in image generation, on the user's
ChatGPT subscription, and its first use: `toast references generate` and MCP
`generate_reference` make a picture from a description and earlier
references' pictures, and keep it as a new reference (CT-0100).

# Why

Demo 01 (CT-0099) needs many trial pictures -- eras, faces, a change of
style inside a movement. The first ones were made by calling Codex outside
the tool, with nothing recorded. The user asked for the adapter on
2026-10-16 and allowed the subscription quota.

# Done

- `providers/codex_image.py`: `CodexImageProvider.generate(prompt,
  references, output)` runs `codex exec --skip-git-repo-check -s read-only
  --json "<instruction>" -i <refs>` with stdin closed, in a temporary
  directory; finds the image under `$CODEX_HOME/generated_images/<thread>/`
  by the `thread.started` event; returns provenance (codex version, thread,
  the file, the instruction, references by sha256, seconds, tokens, cost as
  `subscription quota` with no dollars). Failures and "no image" are errors.
- `references.generate_reference`: the parents' pictures, in order, are what
  the generation is shown; the result is added with `from`, `made_by`
  (asked by whom), the prompt and a `generation` block.
- `toast references generate [--dry-run]`; MCP `generate_reference`
  (open-world, not a read; refusals as answers); `toast doctor` reports
  "Codex image generation" (installed and logged in).
- Docs: `making-a-film.md`, `mcp.md`.
- First real use: `~/films/demo-01/references/2026-10-16-era-trial-1930s`.

# Decisions

- References first, master pictures later: `toast picture` is shaped around
  Qwen's repaint of a render (geometry clauses, padding, edge score); a
  second picture provider there needs an interface, recorded in the roadmap.
- The model is "not reported by codex" in provenance, never a guess; the
  cost is quota, never a made-up price.
- Gemini: not built. The Gemini CLI on this machine is logged in by Google
  account and has no image generation; Gemini's images need an API key with
  billing. Recorded in the roadmap with how to add it.

# Validation

- `tests/test_codex_image.py` (4), against a fake codex that answers with
  the real event shapes: argument order, the picture found by thread,
  provenance; no image and failure are errors and leave no file; not
  installed says the remedy; a generation becomes a reference with lineage.
- `tests/test_mcp.py`: `generate_reference` is not a read.
- Live: one generation in demo-01, 57 s, no findings in `toast references
  list`.
