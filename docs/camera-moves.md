# Camera moves

A catalog of camera moves, shaped like the transition catalog. Each move has:

- **what it says**, when to use it, when to avoid it, and its energy;
- **the geometry it implies** in the scene's plan (SPEC-0005): kind,
  direction, rig and speed;
- **the words a video model is given** for it.

A shot names a move:

```yaml
- n: 3
  camera: CAM-A
  move: {id: push-in}          # kind dolly_in and rig dolly come from the catalog
```

What a shot also says wins over the catalog (`move: {id: push-in, speed:
slow}`). If the shot declares where the camera ends (`move.to`), `toast check`
compares the move it names with the one its start and end poses derive
(`move_kind_mismatch`). A name the catalog does not know is reported
(`move_unknown`), not guessed. When the shot does not describe its camera in
words, generation uses the move's words.

```bash
toast moves [project] [--json]    # the catalog, by category
```

The control room's **Camera moves** room shows the whole catalog.

## Layers

Catalogs layer like transitions:

1. the built-in moves, 32 of them;
2. the paths in `CINE_TOASTER_CAMERA_MOVES_PATH`;
3. the production's own `camera_moves/<id>/move.toml`.

A later layer replaces a move with the same id, so a production can reword
or re-tune a move for its film.

The built-in moves were written for Cine Toaster. aicameramovements.com's
taxonomy was used only as a checklist of names: it states no licence, so none
of its text or examples are used. Moves the plan cannot see (handheld,
body-mounted, first person) imply only a rig, so nothing about them is checked.

## Previews

In the **Camera moves** room, rest the pointer on a move's card to play it.
Every move is played on the same stage (a person, a column and a cabinet
behind, for parallax) from the blocking frames a shot's previs uses, so a
preview shows the geometry the plan will check: a push-in brings the
camera 1.2 m closer, a zoom goes from 28 to 70 mm, an orbit turns the
camera 60° around the subject, a pan turns the aim 35° (80° for a whip), a
dolly zoom sets the lens by the distance so the face keeps its size. A
move whose feel is its rig (handheld, body-mounted) is said to hold still:
the plan cannot show it. Previews are derived on request
(`/api/camera-move-preview?id=…`) and never stored.
