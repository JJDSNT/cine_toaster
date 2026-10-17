# ADR 0030 — Art Direction and independent visual prevalidation

Status: accepted (2026-10-16), implementing SPEC-0016 / CT-0110.

Extend ADR 0029's existing public `assistant` LangGraph CoAgent with Art Direction
and a separate Visual Prevalidation call. Do not add an executor, queue, provider
selection policy or production-workflow engine. The Coordinator and Inception
delegate by capability; model adapters remain injected independently of roles.

Art briefs and advisory reviews are immutable records in `creation/state.json`,
using the same revision/lock/atomic commit and shared application boundary as
Inception. Briefs pin concepts/references and specify checkable criteria. Reviews
pin the exact brief, raster hashes and criterion evidence. Source/brief changes
make reviews and linked human requests stale. No record is a human approval.

Prevalidation gets actual bounded raster attachments in a fresh reviewer request,
without the creator's conversation/quality claims. Optional `ask_images` is a
model-adapter capability: Codex CLI currently implements initial attachments;
text-only adapters fail explicitly. The reviewer still has the same model in
this slice: separation of mission/context is not independent-model corroboration
or objective artistic certification. Doctor reports this transport capability,
not verified authentication/inference or artistic accuracy.

Generation uses existing `generate_reference` jobs, with the exact retained brief
in provenance, per-attempt quota interrupts and non-overwriting adoption. At most
two generations and two visual attempts occur per bounded eight-step art turn.
Failed alternatives remain. A 25-second bounded job wait may return with a real
job still running; further reasoning requires another CoAgent interaction. No
durable autonomous resume, unbounded retries or creative approval is implied.

The Creation GUI displays briefs, findings, stale status and existing human
requests without new authoring forms. Production pixels/gates are not changed
by development acceptance checks. Additional production roles, reference research,
other vision transports and durable resume remain separate follow-ups.
