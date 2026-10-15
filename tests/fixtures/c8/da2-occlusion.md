# da2-occlusion.npz -- a wrong occlusion, kept as a regression fixture (CT-0081 step 4)

Depth Anything V2 Small on a rendered dolly sets a pillar behind the floor along its silhouette (frames 0,
1, 2, 7) and behind a ball where the two are apart (frames 0, 1, 2, 6, 7), with an average error that
passes (AbsRel 0.12 aligned). Kept so the fast suite checks, on real model output, that such an occlusion
is found and refused -- without Blender or the model.

Arrays, 8 frames of 180x320, float16 (the flags are identical to float32's):

- `estimate`: Depth Anything V2 Small's relative depth (inverse z, affine), revision
  `5426e4f0f36572d16453bbda7a8389317b1bef99`, CPU, transformers 5.2.0, torch 2.6.0, input 518;
- `depth`: Blender 5.2.2 Cycles' Z (metres, z along the axis, +inf where nothing was hit), 16 samples;
- `objects`: Blender's object index: 0 nothing, 1 ball, 2 floor, 3 pillar, 4 wall.

Made from `OCCLUSION` in `tests/test_align.py` (rendered at 320x180, 24 fps, frames 1-8; the plate the
render over 0.18 grey in sRGB, FFV1), as `OnARenderedDolly` makes it again when Blender and the models are
here.
