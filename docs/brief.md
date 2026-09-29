# The brief

A scene's brief is what a generation would be told. It is **derived from the
production's records, never written as a brief**, so it cannot contradict
`toast check`: screen sides and the line of action come from the same geometry
the checks read.

```bash
toast brief <project> SC-030              # Auteur Script text; missing slots reported
toast brief <project> SC-030 --json       # every slot with its source
toast brief <project> SC-030 --review P3 [--take ONE-BLINK] --output p3.review.json
```

The scene room shows the brief under the blockout.

## Shape

The brief follows [Auteur Script](https://auteur-script.taruma.my.id/):

- `STAGING` holds what stays true for the whole scene: `[[INTENT]]`,
  `[[LOGIC]]`, `[[AESTHETIC]]` and `[[OPENING]]`.
- `EXECUTION` holds one state per shot, chained with `->`. A state has
  `[CUT IN]`, `[CAM]`, `[BLOCK]`, `[ACT]`, `[DIAL]`, `[AUDIO]` and
  `[STATE OUT]`.

| Source | Where the line comes from |
| --- | --- |
| `authored` | a field of the scene or shot file |
| `screenplay` | the screenplay text the shot covers (SPEC-0006) |
| `derived` | geometry, movement (SPEC-0005), the blocking frame, the cut record (SPEC-0007) |
| `missing` | nothing fills it yet; the text says what to add |

**Shot size** is estimated from the frame height at the subject's distance:
under 0.25 m ECU, 0.45 m CU, 0.8 m MCU, 1.3 m MS, 1.9 m MWS, 4 m WS, and EWS
beyond.

## Reviewing a take

Under each state, pick one of the shot's takes. Its **local** video plays
beside the state's lines, and the line being shown is highlighted as it
plays. The planned times are stretched over the take's real length until a
review re-times them.

The review project is SceneFlow's JSON shape (`scriptText`, `cues`,
`settings`), plus `video`, the take's file relative to the production.
SceneFlow itself plays only YouTube, so `youtubeId` stays empty. Opening the
file in SceneFlow would need a local-video change there.
