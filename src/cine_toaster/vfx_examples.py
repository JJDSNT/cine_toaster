"""A library of example elements, one per delivery modality (CT-0047).

`toast vfx examples <project>` renders a small element with Blender and
derives, with FFmpeg, one copy in each form VFX elements arrive in, each
registered under `vfx_elements/<id>/element.toml`:

- `example-png-sequence`: PNG frames with alpha;
- `example-exr-sequence`: scene-linear half-float OpenEXR frames with alpha
  (OpenColorIO converts them for the picture);
- `example-prores-4444`: a ProRes 4444 video with alpha;
- `example-video-matte`: a colour video and a separate black-and-white matte;
- `example-green-screen`: the element over green, to be keyed;
- `example-blender-project`: the `.blend` itself, rendered headless when used.

Nothing here is a stock asset: the element is made on this machine, so the
examples carry no licence but their own.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .vfx import BLENDER_ELEMENT_SCRIPT

WIDTH, HEIGHT, FRAMES, FPS = 640, 360, 36, 24


def _write(folder: Path, fields: dict[str, Any]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    lines = [f'{key} = {json.dumps(value)}' for key, value in fields.items()]
    (folder / "element.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build(root: Path, *, run=None) -> list[str]:
    """Make the example elements in `root/vfx_elements`; returns their ids."""

    from .titles import blender_binary

    run = run or (lambda command: subprocess.run(command, check=True, capture_output=True))
    blender, ffmpeg = blender_binary(), shutil.which("ffmpeg")
    if not blender or not ffmpeg:
        raise ValidationError("The examples need Blender and FFmpeg (toast doctor says which is missing)")
    library = root / "vfx_elements"
    source = library / "example-blender-project"
    source.mkdir(parents=True, exist_ok=True)
    spec = {"effect": "sparks-burst", "params": {"glow": 3.0, "count": 300}, "width": WIDTH, "height": HEIGHT,
            "fps": FPS, "frames": FRAMES, "formats": ["exr", "png"], "output": str(source / "render")}
    (source / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    run([blender, "--background", "--factory-startup", "--python", str(BLENDER_ELEMENT_SCRIPT), "--",
         str(source / "spec.json")])
    shutil.move(source / "render" / "element.blend", source / "sparks.blend")
    common = {"category": "sparks", "loop": False, "source": "rendered by Cine Toaster's example builder (Blender)",
              "license": "made for this production"}

    _write(source, {"id": "example-blender-project", "label": "Sparks (.blend project)", **common, "blend": "alpha",
                    "project": "sparks.blend", "frames": FRAMES})

    png = library / "example-png-sequence"
    shutil.copytree(source / "render" / "png", png / "frames", dirs_exist_ok=True)
    _write(png, {"id": "example-png-sequence", "label": "Sparks (PNG sequence)", **common, "blend": "alpha",
                 "file": "frames/f_%04d.png"})

    exr = library / "example-exr-sequence"
    shutil.copytree(source / "render" / "exr", exr / "frames", dirs_exist_ok=True)
    _write(exr, {"id": "example-exr-sequence", "label": "Sparks (OpenEXR, scene-linear)", **common, "blend": "alpha",
                 "file": "frames/f_%04d.exr", "colorspace": "Linear Rec.709 (sRGB)",
                 "view": "ACES 2.0 - SDR 100 nits (Rec.709)"})

    frames = str(png / "frames" / "f_%04d.png")
    prores = library / "example-prores-4444"
    prores.mkdir(parents=True, exist_ok=True)
    run([ffmpeg, "-v", "error", "-y", "-framerate", str(FPS), "-i", frames, "-c:v", "prores_ks", "-profile:v", "4444",
         "-pix_fmt", "yuva444p10le", str(prores / "sparks.mov")])
    _write(prores, {"id": "example-prores-4444", "label": "Sparks (ProRes 4444 with alpha)", **common,
                    "blend": "alpha", "file": "sparks.mov"})

    matte = library / "example-video-matte"
    matte.mkdir(parents=True, exist_ok=True)
    run([ffmpeg, "-v", "error", "-y", "-framerate", str(FPS), "-i", frames, "-filter_complex",
         "[0:v]format=rgba,split[c][a];[c]format=yuv420p[colour];[a]alphaextract,format=yuv420p[matte]",
         "-map", "[colour]", "-c:v", "libx264", "-crf", "16", str(matte / "sparks.mp4"),
         "-map", "[matte]", "-c:v", "libx264", "-crf", "16", str(matte / "sparks_matte.mp4")])
    _write(matte, {"id": "example-video-matte", "label": "Sparks (video + matte)", **common, "blend": "alpha",
                   "file": "sparks.mp4", "matte": "sparks_matte.mp4"})

    green = library / "example-green-screen"
    green.mkdir(parents=True, exist_ok=True)
    run([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=0x00B140:s={WIDTH}x{HEIGHT}:r={FPS}",
         "-framerate", str(FPS), "-i", frames, "-filter_complex", "[0:v][1:v]overlay=shortest=1,format=yuv420p",
         "-c:v", "libx264", "-crf", "16", str(green / "sparks_green.mp4")])
    _write(green, {"id": "example-green-screen", "label": "Sparks (green screen)", **common, "blend": "key",
                   "key_color": "0x00B140", "file": "sparks_green.mp4"})

    shutil.rmtree(source / "render", ignore_errors=True)
    (source / "spec.json").unlink(missing_ok=True)
    return ["example-png-sequence", "example-exr-sequence", "example-prores-4444", "example-video-matte",
            "example-green-screen", "example-blender-project"]
