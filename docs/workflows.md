# Workflows and gates

A **workflow** takes a generation block from its master pictures to takes. It
stops for a person where a person has to look, and nothing is animated from
a picture nobody approved.

```text
picture (each master the block uses) → approve it → generate the block → slice into takes
```

## In the control room

The scene room's **Workflow** panel lists the scene's runs:

- **Start for block N** begins a run.
- Each run shows its steps: done, skipped, running, waiting for you, or
  failed.
- A picture step is **skipped** when the master already has a picture. It
  is made (a paid edit) only when there is none.
- A **gate** shows the render and every candidate side by side, each with
  what it was made from. You then choose one of:
  - **Approve this**: the version becomes the master's picture, and the run
    goes on to generate and slice by itself. A reason is optional.
  - **Ask for another version**: a new edit with the next seed, then the
    question again with every version. Say **what is wrong**: tick a
    reason, write one, or both.
  - **Reject (end the run)**: the run stops. Say what is wrong here too.

The canvas (`/app/`) shows each block's latest run as a card beside the
block, highlighted while it waits for you.

## From the terminal

```bash
toast workflow start <project> 1-02A 2      # runs until it waits for you, or ends
toast workflow list <project> [scene]
toast gate decide <project> 1-02A <gate> --approve cenas/.../pmA-1.png --why "on her mark"
toast gate decide <project> 1-02A <gate> --changes --reason subject_moved --why "head left of the render's mark"
toast gate decide <project> 1-02A <gate> --reject --reason identity
toast workflow resume <project> 1-02A <run>  # after the runtime restarted
toast workflow cancel <project> 1-02A <run>
```

## What is kept

Runs and gates live in the scene's `state.json`, beside its other decisions.
They are production records, not job-store state. Every decision records
who made it, when, and why.

The approved version is the master's picture from then on, for generation
plans, slicing and briefs. Nothing is copied or renamed, so the earlier
versions stay available to compare. See SPEC-0009.
