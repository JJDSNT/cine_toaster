---
id: CT-0058
title: FinOps steps 2-3 -- what Runpod billing exposes; provider execution ids
type: work
status: done
owner: unassigned
created_at: 2026-10-04
updated_at: 2026-10-04
tags:
  - finops
  - providers
---

# What

Backlog "Now" item 4 (`docs/finops.md` § Implementation path, steps 2-3).
Step 2 inspects, read-only, what Runpod's billing really exposes. Step 3
ensures every paid job records the provider's execution id in its
provenance.

# Done

- Step 2: read live through the Runpod MCP tools (`list-billing`,
  `list-serverless-billing`, `list-endpoints`), with no mutation. The verified
  facts are in `docs/finops.md` § "Verified on 2026-10-04".
  - Billing is per endpoint per time bucket, and no line exists per job.
  - Amounts only: no usage seconds and no rate.
  - September: US$36.44 serverless over 8 endpoints. The Cine Toaster ledger
    recorded about US$0.58, so most spend came from tools outside Cine
    Toaster.
- Step 3: the id was already kept in `<take>.job.json` and in the spend ledger
  (`remote`).
  - It now also sits in the provenance itself. `execution: {provider, endpoint,
    id, worker, status, delay_ms, execution_ms}` is added for video generations
    (block and shot) and picture derivations.
  - These are the only paid remote jobs.

# Decisions

- A job's provider-authoritative cost can only be allocated: the endpoint's
  billed hour is shared among the jobs that ran in it, in proportion to their
  `delay + execution`. The rest stays explicitly unattributed (idle workers,
  disk, spend from outside Cine Toaster).

# Validation

`tests/test_generation.py` and `tests/test_pictures.py` assert the execution
block (14 tests). Full suite before commit.

# Remains

- Step 4: a read-only Runpod cost observation adapter (REST, API key from
  `~/confyui/.env`).
- Step 5: hourly allocation and reconciliation health (unattributed amount,
  jobs with no observation).
