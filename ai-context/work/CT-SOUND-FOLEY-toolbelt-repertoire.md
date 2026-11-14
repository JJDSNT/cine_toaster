---
id: CT-SOUND-FOLEY
title: Sound design and Foley toolbelt repertoire
type: work
status: ready
owner: project
created_at: 2026-11-13
updated_at: 2026-11-13
tags:
  - audio
  - foley
  - sfx
  - toolbelt
  - agents
---

# Sound design and Foley toolbelt repertoire

## What
Expand Cine Toaster's **discoverable repertoire** of sound-design tools and
approaches. Each filmmaker and their production agent should be free to discover,
experiment with and combine tools that serve their creative goals. This record
is a research entry, **not** an implementation mandate, mandatory workflow or
permission to install software or incur costs.

References are catalogued in [External references](../references.md):
Earshot, Clipwing Real SFX, Openverse API, reeleehq/foley and foley-skill.

## Why
Different scenes may call for existing recordings, synthesized sounds, layered
Foley or silence. The toolbelt should describe available possibilities, not
prescribe one method. Preserve editorial control, reproducible timing, license
and source attribution, editable audio layers and project provenance.

## Done
- Recorded the five references and candidate capabilities in the external
  repertoire catalogue.
- Established that repository research must not be mistaken for production
  agent runtime access or an adopted feature.

## To do
1. Audit the current Cine Toaster audio tools, stems, timeline, sound generation,
   media adapters, runtime skills and tool exposure. Record capabilities already
   present before proposing new ones.
2. Verify each candidate's repository, current license, supported operations,
   interfaces (CLI/API/MCP), dependencies, resource needs, output formats and
   maturity; verify the exact Real SFX skill within Clipwing/skills.
3. Map overlapping capabilities: search existing audio, synthesize/generate,
   analyze, audition, spot events, synchronize, layer, mix and export. Avoid
   prescribing an order or selecting a preferred vendor globally.
4. Evaluate agent discovery: what metadata and capability declarations would
   allow a **production** agent to find and compare approved runtime tools
   under project permissions and budgets? Development references in
   `ai-context/` must not be injected into production-agent context.
5. Explore minimal integration behind existing typed commands/adapters,
   preserving film-owned decisions and human review. Check licensing and
   attribution for each retrieved recording.
6. If experimentation is approved, compare quality, timing accuracy, costs,
   ease of revision and reproducibility on representative shots. Record what
   worked and the conditions where it did not; do not generalize one film's
   creative choices into defaults.

## Decisions
- Toolbelt is a repertoire for filmmaker-and-agent discovery, not a fixed
  pipeline or a required list of integrations.
- No new Foley engine, mandatory skill, audio mixer or provider-specific
  Core dependency is approved by this document.
- Candidate tools remain optional until their interfaces, licenses and actual
  use are verified. No paid calls or installations without authorization.
- Agent runtime tools remain typed, permissioned and project-scoped.

## Validation
Documentation only. No runtime compatibility, licenses, tools or workflows
have been tested as part of this record.
