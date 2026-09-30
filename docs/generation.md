# Generating

## Master pictures

A master picture is made by **editing** another picture, usually a render
of the 3D set, with the cast's faces. It is not generated from words: the
render decides where everything is, and the cast sheets decide who.

```yaml
- n: mA
  derive:
    from: rA                   # a shot or master whose picture is edited, or a file
    with: [CLAIRE]             # whose face; the scene's `cast` picks the variant
    request: The head on the pillow becomes the young woman in image 2, ...
```

```bash
toast picture <project> 1-02A Pma --dry-run          # the source, the faces, the prompt, the estimate
toast picture <project> 1-02A Pma --env-file ~/.env  # one paid edit -> work/pmA-1.png, beside pmA.png
```

The editor is told that image 1 alone decides the geometry. References are
padded to the frame's proportion, and the size follows the source (see the
`qwen-image-edit` knowledge profile for why). Each version records its
source and faces with digests, the request, the prompt, the seed, the cost,
and an **edge score**: the edges kept from the source.

A score under 17 means the frame was recomposed. A good score does not
prove the people stayed where the render put them, so look before using a
picture. The scene's **Pictures** panel shows every version, what it was
made from, and what a new edit would be given.

# Generating a block

(A shot outside any block is generated the same way, on its own:
`toast generate <project> SC-030 P7` plans it as a one-shot generation, and
its result is a **take** of the shot (`GEN`, `GEN-2`…), with no slicing. A
length that is not a whole number of seconds is rounded up, and the cut
trims the rest.)

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
- **A retry never pays twice for the same request.** While a generation
  waits at the remote end, its remote job is remembered under
  `~/.local/state/cine-toaster/remote/`, keyed by the request itself:
  scene, block or shot, seed, prompt and pictures. If the runtime dies, a
  retry finds that job and waits for it instead of sending it again, and
  the ledger counts it once. Once the result is adopted, or the job fails
  or is cancelled, the record is dropped, so asking again really asks
  again.
- The ledger is `~/.local/state/cine-toaster/spend.json`. Deleting it
  forgets history and refuses generation until a budget is set again.

## What is kept

A generation never replaces the production's own clip. It becomes
`b<id>-<n>.mp4` beside it, with:

- `.job.json`: the platform's record, including the time billed;
- `.provenance.json`: the plan, the guides with their digests, the prompt,
  the seed, the cost and the job.

## Seeing it in the control room

The scene's **Blocks** panel shows every version of a block.

- **What would be sent…** shows exactly what a generation would be given,
  and nothing is sent until you press **Send** there:
  - the starting picture and each guide, with the frame and time it holds
    and the picture's digest;
  - the prompt, split by shot, followed by what holds across the block;
  - the length, the seed, the estimate, and the budget spent so far.
- Under each version, **What … was made from** shows the same, read from
  the record kept beside the clip, with the real cost and GPU time. A clip
  made outside Cine Toaster shows only the platform's job, and says that
  what was sent was not recorded.
- In the comparison room, each take made here has **What was sent**:
  - a slice shows where it was cut, and the block's record;
  - a converted voice shows the recording it was converted to (playable),
    and the likeness before and after. Slicing a version gives
takes named `BLOCK-<id>V<n>`, each carrying the generation's record.

Credentials are read from the environment, or from `--env-file`. Neither is
ever printed.
