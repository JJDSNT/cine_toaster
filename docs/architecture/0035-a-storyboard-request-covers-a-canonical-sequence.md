# ADR 0035: A storyboard request covers a canonical sequence; one consent sends a batch

Status: accepted (2026-10-17). Amends ADR 0032 (SPEC-0018).

## Context

The director's unit of work and review is the sequence (CT-0112's correction,
the work policy). Producing Demo 01, the director approved a storyboard
request whose scope was SC-010 P1-P3 only -- written the day before -- and
was then asked to continue a three-shot study: one scene does not give the
visual context to judge anything. The handoff could not express more: its
target was one scene and its shots. Art Direction's turn (8 steps, 2
generations, one consent per image) could not carry a 24-shot sequence
either: 21 consents and a dozen turns.

## Decision

1. **A handoff target may be a canonical sequence**: `{sequence, label,
   scenes: [{scene, shots}]}`, resolved from the production's declared
   sequences (`work_structure`), in their declared order, every shot of every
   member scene. Membership is never inferred from numbering: Singular's
   Genebra is 1-01..1-04 with 1-02A/B/C because the film declares it. A
   proposal asks for it with `proposal.sequence`; a target is only authority
   if it equals the sequence as declared now. Scene targets remain.
2. **Art Direction works the sequence scene by scene**: it sees the whole
   sequence (what each scene still lacks) and one focused scene (the first
   with missing drawings, or the one it asks for), and may publish to any
   shot of the target and nowhere else.
3. **One consent for a batch**: `plan_batch` plans one drawing per missing
   shot (at most 30), `generate` asks once with the list, and every job is
   sent together; each job not yet kept is left to Generation Operations,
   which brings each finished picture back to the role with the shot it was
   planned for. Nothing outside the consented plans is generated.
4. **The review request covers the sequence**: every shot of the target must
   have a retained drawing, and every current drawing must have been seen by
   a current successful visual review (inspection runs in batches of eight).
5. **A newer request supersedes a handoff**: the old one stays in the journal
   as history and leaves the AI-work list.

## Consequences

- The director approves once, sees progress as coverage (drawn / shots), and
  reviews the sequence whole.
- The batch and the handoff it serves are kept across turns in the thread's
  state; a restart of the assistant server loses them (the waits survive, the
  records do), recorded with Generation Operations' limits.
