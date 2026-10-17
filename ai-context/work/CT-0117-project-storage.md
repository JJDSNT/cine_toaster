---
id: CT-0117
title: Project Storage visibility and capacity
type: work
status: ready
owner: project
created_at: 2026-10-17
updated_at: 2026-10-17
tags:
  - storage
  - ux
  - production-operations
---

# CT-0117 — Project Storage

## What
Add project storage visibility to the production UI: managed project footprint, free disk capacity, total volume capacity, and a categorized breakdown of source media, generated assets, renders, proxies, caches, and intermediates. Show external referenced media separately. For split storage, show per-volume availability (including network volumes and remote Runpod storage when supported).

## Why
A filmmaker needs to know both how much space a production consumes and whether the render destination has enough space to complete work. This is production awareness, not only FinOps.

## Done
- Requirement captured and linked to GitHub issue #1 (as CT-0098 on `main`; renumbered CT-0117 on the merge of 2026-10-17, CT-0098 being already used on `demo-01-foundations`).

## To do
- Relate to Generation Operations (CT-0115): a batch preflight can check the destination volume, local or RunPod network volume, before sending.
- Audit existing project media inventory, storage paths, runtime queries, and UX surfaces before designing the command/query/API contract.
- Specify measurement rules: physical vs logical bytes, hardlinks/shared assets, referenced assets, offline volumes, permissions, and mount boundaries.
- Implement efficient incremental or cached accounting with explicit refresh; do not rescan the full tree on each UI request.
- Expose project footprint, free/total capacity for each relevant volume, breakdown and low-space warnings through shared application queries (CLI, API, UI, agents).
- Integrate with preflight checks for generation/render jobs, with explicit unknown estimates; distinguish local from remote storage.
- Identify reclaimable caches without automatically deleting source media; validate on a multi-volume production and unavailable mount.
- Update project status and UX documentation when implemented.

## Decisions
- Filesystem production records remain authoritative; usage indexes are disposable operational data.
- Never infer free disk capacity from project size; query the destination filesystem.
- Keep externally referenced assets distinct from project-managed files.
- GitHub issue: https://github.com/JJDSNT/cine_toaster/issues/1

## Validation
Not implemented; acceptance tests to be defined during implementation.
