# The production canvas

`/app/` in the control room (or the **Canvas** link in its navigation)
draws the production as cards:

- a **scene** starts each row;
- its **shots** follow in order. Each shot card shows its best picture: the
  master still, then the selected take, then the blocking frame computed from
  geometry. It also shows its camera, its duration, who speaks, and whether
  something moves;
- a shot's **takes** hang below it, and the selected one is marked;
- a **cut** is the line between two shots. It is labelled with its type (cut,
  match, J- or L-cut…) and its transition, and coloured when a check found
  something wrong with it;
- a faint dotted line above the cards leads from a shot to each shot made
  from its picture (lineage, **Made from** in the header hides them); a
  decided one is solid;
- a dashed line leads from one scene to the next.

Select a card or a cut to see its record. The canvas follows the production
live: select a take in the control room and the card updates.

## Changing the film from the canvas (plan step 13)

- **A cut.** Select it to get a form with these fields:
  - the type (cut, match, on action, J, L, smash, jump, continuation);
  - whether the shot opens on the previous last frame;
  - why;
  - a transition from the catalogue, with its duration and its reason.

  **Save the cut** records a decision. The canvas draws it with ✎, and the
  record keeps what the breakdown says. **Back to the breakdown** undoes the
  decision, and the history keeps both. The breakdown file itself is never
  rewritten: a decision stands over it (ADR 0006), as a chosen take does.
- **What a shot is made from.** Select a shot and open **Change what it
  is made from**: the shot whose picture it starts from and, for a derived
  picture (`derive`), whose faces the cast lends. **Save the reference**
  records a decision over the breakdown, like a cut: the card shows
  `from N ✎`, the breakdown's own lineage stays in the record, and **Back
  to the breakdown** undoes it. How it is made from it (the same picture,
  its last frame) stays the breakdown's. A shot made from itself, a loop
  (P1 from P3 from P2 from P1), an unknown shot or file and a cast member
  without a sheet are refused. Generation, master pictures and the slices'
  reference pictures read the decided lineage.
- **A workflow.** A shot of a generation block with no run in progress
  offers **Start the workflow for block N**. The run then appears as a card
  beside the scene.

Every change is the same command the control room, the CLI (`toast cut set
|clear`, `toast reference set|clear`, `toast workflow start`) and the assistant use. It is sent against
the scene's revision the canvas was drawn from, so a change made on a stale
view is refused instead of overwriting someone else's. Picture and take
decisions stay in the scene room and the comparison room, where the
candidates are shown side by side.

Where cards sit is **computed**, not stored: the same film always draws the
same way, and there is no layout to save, merge or lose.

It is built with React and React Flow (ADR 0015). Building it needs Node 20+,
but running Cine Toaster does not:

```bash
make ui            # builds the canvas and the screenplay editor into the package
make ui-test       # typecheck and layout tests
cd frontend && npm run dev   # live development, next to `toast serve`
```
