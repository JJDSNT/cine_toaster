# The production canvas

`/canvas/` in the control room (or the **Canvas** link in its navigation)
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
- a dashed line leads from one scene to the next.

Select a card or a cut to see its record, with a link to the room where it is
changed. The canvas is **read only**. It follows the production live: select
a take in the control room and the card updates.

It is built with React and React Flow (ADR 0015). Building it needs Node 20+,
but running Cine Toaster does not:

```bash
make ui            # builds the canvas into the package
make ui-test       # typecheck and layout tests
cd frontend && npm run dev   # live development, next to `toast serve`
```
