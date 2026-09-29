+++
id = "runpod-serverless"
title = "RunPod serverless endpoints"
kind = "platform"
version = "REST v1/v2, 2026"
measured_with = "SINGULAR generation sessions, 17–20 Sep 2026 (singular/docs/SINGULAR-PROXIMOS-PASSOS.md)"

[[claims]]
id = "silent-gpu-swap"
claim = "When the chosen GPU runs out in a data centre, the platform can allocate another kind (a 'RTX PRO 6000 Blackwell MIG 2g.48gb' slice) where the LTX image fails at 0 s."
status = "measured"
measured_on = "2026-09-18"
evidence = ["SINGULAR block 1 session"]
impact = "high"
workaround = "Pin the endpoint's allowed GPU types."

[[claims]]
id = "job-vanishes"
claim = "A recorded job can disappear from the queue when the endpoint is drained or reconfigured; its status then returns HTTP 404."
status = "measured"
measured_on = "2026-09-18"
evidence = ["SINGULAR block 1 session"]
impact = "medium"
workaround = "Treat 404 as a terminal failure and resubmit (providers/runpod.py does)."

[[claims]]
id = "volume-pins-region"
claim = "A network volume pins the endpoint to its data centre, where the GPU may be scarce."
status = "measured"
measured_on = "2026-09-18"
evidence = ["SINGULAR: 100 GB volume in EU-NL-1"]
impact = "medium"

[[claims]]
id = "secrets-in-env"
claim = "An endpoint's environment variables are returned in plain text to anyone who can read the endpoint."
status = "measured"
measured_on = "2026-09-29"
evidence = ["endpoint read during CT-0039"]
impact = "high"
workaround = "Store tokens as RunPod secrets, never as plain environment values."
+++

The platform side of generation: what happens between submitting a job and
getting a clip back. These are facts about the platform, kept apart from the
model's own behaviour (`ltx-2.5`).
