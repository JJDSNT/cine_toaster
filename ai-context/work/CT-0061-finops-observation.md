---
id: CT-0061
title: FinOps steps 4-5 -- read Runpod billing, allocate billed hours to known jobs
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

`docs/finops.md` steps 4 and 5: a read-only Runpod cost observation, and the
reconciliation of provider charges with known jobs. CT-0058 verified that
Runpod bills per endpoint per hour and never per job, so a job's
provider-authoritative cost is an allocation.

# Done

- `providers/runpod_billing.py`: reads `GET
  https://api.runpod.io/v2/billing/serverless` and returns provider-neutral
  observations. It sends its own User-Agent, because Cloudflare answers
  Python's default with 403, error 1010.
- `finops.py`:
  - `reconcile` gives each billed hour to its known jobs in proportion to
    their seconds (`allocated`, next to `measured`, with the overhead);
  - hours with no known job are `unattributed` and listed;
  - jobs that cannot be placed are `unobserved`, with the reason;
  - health figures: billed, attributed, unattributed, reconciled share, and
    `fetched_at`.
- `film_jobs` and `merge`: the job records a film keeps beside its takes,
  archived ones included, each job id counted once and whoever ran them. They
  complete ledger entries that lack an endpoint.
- The spend ledger now records `endpoint` and `seconds`. Runpod job records
  now record `finished_at`.
- `toast finops [--days] [--project] [--env-file] [--json]`, cached as
  disposable operational state.

# Decisions

- **Whole bucket allocated.** A billed hour is given entirely to the jobs in
  it, idle tail included: that is what running them cost. The measured cost
  stays beside the allocation, so the overhead is visible and not hidden.
- **No guessing.** An entry with no endpoint is not matched by time alone. An
  older film record without `finished_at` uses the file's time and says so.
  `toast migrate` keeps file times (`copy2`), so they match SINGULAR's
  originals.
- **The film's jobs.** A job counts as the film's whoever ran it: SINGULAR's
  pre-Cine Toaster LTX jobs are the film's spend.

# Validation

- Tests: `tests/test_finops.py` (allocation, unattributed, unobserved,
  film records, merge, deduplication) and the generation test (`finished_at`).
- Live read-only run, 30 days:
  - billed US$ 36.44; attributed US$ 9.79 (27%) to SINGULAR's 138 job
    records; unattributed US$ 26.65;
  - checked by hand: an LTX block measured at US$ 0.557 was billed US$ 0.217,
    so the assumed LTX rate is about 2.6 times too high.
- Full suite before commit.

# Remains

- **Correct the assumed LTX rate.** Use the observed rate (billed GPU per
  billed second, over enough hours) rather than the guessed one, so budget
  checks stop overcharging. The budget ceiling stays.
- **The other endpoints** (Krea, Qwen, Wan, lip-sync, music) have no job
  records in SINGULAR. Their spend stays unattributed: it predates Cine
  Toaster.
- **Step 6 onwards:** expose cost status through the API and MCP, then the
  console, once the data is used.
