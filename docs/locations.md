# Locations and the backlot

A **location** is a set declared once: its room, its marks, the camera
positions tested on it, and what it looks like. The scenes shot there name it,
and only add what is theirs.

```yaml
# locations/listening-station/location.yaml
id: LISTENING-STATION
label: The listening station
room: [6.0, 4.5, 3.2]
marks:
  - {id: HALFWAY, x: 2.6, y: 2.3}
cameras:
  - {id: CAM-A, x: 3.4, y: 0.9, height: 1.05, target: [4.1, 2.2], lens_mm: 50}
references:
  - {path: plates/cam-a.png, kind: plate, camera: CAM-A}
```

```yaml
# a scene shot there
location: LISTENING-STATION
geography:
  subjects: [...]            # who is in the room: the scene's own
  axis: [MARA, SPEAKER]
  cameras:
    - {id: CAM-A, shots: "3"}   # the set's camera, covering shot 3 here
```

- **What the scene takes from the location:** the room, the marks and the
  set pieces (`set_pieces`, see continuity-checks.md). A scene may add a
  piece or move one by id; a moved piece is reported like a moved mark.
- **Cameras:** a scene camera entry with only an id takes the location's
  camera. An entry with a position replaces it for that scene.
- **Plates as the start of a picture:** a plate is the empty set,
  photographed or rendered from where one of the set's cameras stands. A
  shot's master picture can be made from it: `derive: {from: location:CAM-A,
  with: [MARA], request: ...}`, or `from: location` for the plate of the
  shot's own camera. The edit then puts the cast into the real room, with
  its geometry kept. A plate that does not exist is reported by the checks
  (`plate_missing`, warning) before any edit is paid for. On the canvas,
  **Change what it is made from** lists the scene's plates beside its shots.
- **Plates as the start of a picture:** a plate is the empty set,
  photographed or rendered from where one of the set's cameras stands. A
  shot's master picture can be made from it: `derive: {from: location:CAM-A,
  with: [MARA], request: ...}`, or `from: location` for the plate of the
  shot's own camera. The edit then puts the cast into the real room, with
  its geometry kept. A plate that does not exist is reported by the checks
  (`plate_missing`, warning) before any edit is paid for. On the canvas,
  **Change what it is made from** lists the scene's plates beside its shots.
- **Checks:** a scene that moves one of the set's marks or cameras is told
  (`location_override`, advice), so a real change and a drift both show. A
  location the production does not have is an error (`location_unknown`).
- **Where it shows:** the **Locations** room draws each set's plan (room,
  marks, cameras with their field of view, set pieces), lists its cameras,
  marks and pieces, shows its plates, links the scenes shot there, and says
  where a pinned set stands against the backlot. The scene room says where
  the scene is set and which other scenes are shot there. The assistant knows every location and its
  scenes.

## The backlot

A backlot is a folder of locations shared across productions, found through
`CINE_TOASTER_BACKLOT`. A production does not follow it live: it **pins a
copy**.

```bash
toast backlot list                          # what the backlot offers
toast backlot pin <project> harbour-office  # copy it in, with where it came from
toast backlot status <project>              # has the backlot moved on? was the copy edited here?
toast backlot pin <project> harbour-office --update   # take the backlot's newer version
```

Editing the backlot never changes a film by itself. See SPEC-0010.
