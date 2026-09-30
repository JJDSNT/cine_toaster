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

## Aerial moves

Six moves are flown (`rig: drone`): **top shot** (straight down), **rise and
reveal** (from a person up over the place to the view beyond), **drone
descend** (its reverse), **aerial orbit**, **flyover** and **aerial
tracking** (keeping pace with a vehicle), beside the drone push in and pull
back. They are previewed outdoors: a person on a street, buildings, a road
with a car, a lake beyond.

A scene flown over is outdoors, and its camera aims down. Two plan fields
say so:

```yaml
geography:
  room: [400, 300]          # the part of the city the plan covers, in metres
  exterior: true            # ground only: no walls, no ceiling to rise through
  subjects:
    - {id: KAEL, label: Kael, x: 180, y: 120, eye_height: 1.7}
  marks:
    - {id: LAKE, x: 200, y: 280}
  cameras:
    - {id: DRONE, x: 180, y: 116, height: 1.8, target: KAEL, lens_mm: 28, shots: "1"}

shots:
  - n: 1                    # the rise from Kael over the city, framing the lake
    move:
      id: rise-and-reveal
      to: {x: 180, y: 60, height: 60, target: LAKE, target_height: 0}
```

`target_height` is how high the camera aims: 0 is the ground (the lake,
the road), and without it the camera aims at its subject's eyes, or level.
A change of aim height with the camera in place is derived as a tilt. For a
car on a road, the car is a subject of `kind: object` that moves
(`subjects_move`), and a drone camera aimed at it with `target_height: 0`
keeps pace with it (`move: {id: aerial-tracking, to: {...}}`).
