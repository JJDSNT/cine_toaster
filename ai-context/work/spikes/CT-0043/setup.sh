#!/bin/bash
# A demo copy set up like tests/test_workflows.py.
S=$(cd "$(dirname "$0")" && pwd); F=$S/film
rm -rf "$F" "$S"/state "$S"/*.sqlite* "$S/sent.log"; cp -r /home/jaime/cine_toaster/examples/demo-project "$F"
D=$F/scenes/030-echo-chamber; mkdir -p "$D/blockout"
"$S/venv/bin/python" - "$D" <<'PY'
import sys; from pathlib import Path; from PIL import Image
d = Path(sys.argv[1])
Image.new("RGB", (704, 384), "grey").save(d / "blockout" / "cam-a.png")
Image.new("RGB", (1280, 704), "red").save(d / "work" / "p02.png")
t = (d / "scene.yaml").read_text()
t = t.replace("  - n: 2\n", "  - n: 2\n    block: A\n", 1)
t = t.replace("  - n: 3\n", "  - n: 3\n    block: A\n    derive:\n      from: blockout/cam-a.png\n      with: [MARA]\n      request: The figure becomes the woman in image 2.\n", 1)
(d / "scene.yaml").write_text(t)
PY
[ -f "$S/made.mp4" ] || ffmpeg -v error -y -f lavfi -i "color=c=red:s=64x36:r=24:d=8.33" -f lavfi -i "color=c=blue:s=64x36:r=24:d=11.67" -filter_complex "[0:v][1:v]concat=n=2:v=1:a=0[v]" -map "[v]" -c:v libx264 -pix_fmt yuv420p "$S/made.mp4"
