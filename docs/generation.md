# Generating a block

A **block** is a run of consecutive shots made in one generation
(`block: <id>` on each shot). Cine Toaster builds everything the generation
is given from the production's records, shows it, and sends it only when
the budget allows.

```bash
toast budget set 2                                   # the ceiling, in US dollars
toast generate <project> 1-02A 2 --dry-run           # the plan, the prompt and the estimate; nothing is sent
toast generate <project> 1-02A 2 --env-file ~/.env   # one paid generation -> work/b2-1.mp4
toast slice <project> 1-02A 2 --clip b2-1.mp4        # that version, sliced into one take per shot
toast budget                                         # spent so far, and the last entries
```

## What is sent

- **Starting picture:** the first shot's reference picture. That is its
  still, its `p<n>.png`, or the image of the shot it is made from
  (`from`/`usa`, e.g. `pmB.png`).
- **Guides:** the first picture again at frame 0, and each later shot's
  picture at its cut. Cuts fall on multiples of 8 frames.
- **Length:** the sum of the shots' `generated_seconds`, in whole seconds
  from 1 to 20.
- **Prompt:** written in LTX 2.5's grammar (`providers/ltx_prompt.py`). For
  each shot it gives the picture (`picture`, or the picture of the shot it
  is made from), the camera (`camera_text`), the action, and the lines.
  Each line has the speaker as the scene refers to them (`refer_as`), the
  delivery, and the voice. The voice is the identity from the cast sheet,
  then how it sounds in this scene (`voice_state`). Setting, light and
  voices are held across the cuts.

## Money

- Nothing is generated while no budget is set.
- A generation whose estimate would take the total past the budget is
  refused before anything is sent. The estimate uses the production's
  `generation_rates` for the endpoint, or the provider's assumed rate.
- What the platform bills is written to the ledger even when the
  generation fails or is cancelled. Cancelling the job also cancels the
  remote job.
- The ledger is `~/.local/state/cine-toaster/spend.json`. Deleting it
  forgets history and refuses generation until a budget is set again.

## What is kept

A generation never replaces the production's own clip. It becomes
`b<id>-<n>.mp4` beside it, with:

- `.job.json`: the platform's record, including the time billed;
- `.provenance.json`: the plan, the guides with their digests, the prompt,
  the seed, the cost and the job.

The Blocks panel shows every version of the block. **Generate a new version…** shows the
plan, the estimate and the budget, and asks before sending. Slicing a version gives
takes named `BLOCK-<id>V<n>`, each carrying the generation's record.

Credentials are read from the environment, or from `--env-file`. Neither is
ever printed.
