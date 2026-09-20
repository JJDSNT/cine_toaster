---
id: CT-0003
title: Standardize AI context frontmatter
type: work
status: done
owner: Codex
created_at: 2026-09-20
updated_at: 2026-09-20
tags:
  - ai-context
  - metadata
  - tracker
---

# What

Add consistent YAML frontmatter to every Markdown document under `ai-context/`
and document the metadata contract.

# Why

The directory is the memory and tracker for Cine Toaster development. Stable,
structured metadata makes its documents discoverable and allows future tools or
agents to query type, lifecycle, ownership, dates, and tags without inferring
them from prose.

# Done

- Defined common fields in `ai-context/README.md`.
- Added IDs, document types, lifecycle status, ownership, dates, and tags to all
  consolidated context and development guides.
- Extended existing work records and the work template with `type` and `tags`.

# To do

- Nothing remains in this work record.

# Decisions

- Common fields are `id`, `title`, `type`, `status`, `owner`, `created_at`,
  `updated_at`, and `tags`.
- Work records retain their dedicated workflow statuses.
- Consolidated documents use lifecycle values appropriate to their type, such as
  `active`, `accepted`, or `current`.

# Validation

- Verified that every Markdown file under `ai-context/` starts with `---`.
- Inspected all `id`, `type`, and `status` fields; document IDs are unique, with
  `CT-NNNN` reserved as the template placeholder.
- `git diff --check` passed.
- `PYTHONPATH=src python3 -m unittest discover -s tests -v` passed all 8 tests.
