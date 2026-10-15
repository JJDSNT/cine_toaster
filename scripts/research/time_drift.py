"""CT-0079's measurement. Usage: PYTHONPATH=src python scripts/research/time_drift.py <folder> <shots> <rate>

A film at 30000/1001 of N shots, each take flashing white at its frame 20 with a click at the same instant;
cut by the assembly, then measured: does each click land on its flash, and does the gap grow?"""
import subprocess, sys, json
from pathlib import Path
import numpy as np
from cine_toaster.assembly import plan_scene, render
from cine_toaster.project import load_production

root = Path(sys.argv[1]); N = int(sys.argv[2]); rate = sys.argv[3]  # e.g. 30000/1001
num, den = (int(x) for x in rate.split("/"))
root.mkdir(parents=True, exist_ok=True)
(root / "project.yaml").write_text("id: t\ntitle: T\npaths:\n  scenes: scenes\n")
work = root / "scenes" / "010" / "work"; work.mkdir(parents=True, exist_ok=True)
(root / "scenes" / "010" / "scene.yaml").write_text("scene: S1\nshots:\n" + "".join(
    f"  - n: {i}\n    duration: 2\n    label: Shot {i}.\n" for i in range(1, N + 1)))
flash_frame = 20
click = flash_frame * den / num  # seconds, exact in the take
for i in range(1, N + 1):
    take = work / f"c{i:02d}.mp4"
    if take.exists():
        continue
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"color=c=black:s=160x90:r={rate}:d=2,geq=lum='if(eq(N,{flash_frame}),255,16)':cb=128:cr=128",
                    "-f", "lavfi", "-i",
                    f"aevalsrc='if(between(t,{click},{click}+0.002),0.9,0)':s=48000:d=2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", "-shortest",
                    str(take.with_suffix(".mov"))], check=True)
    take.with_suffix(".mov").rename(take)
plan = plan_scene(root, load_production(root)["scenes"][0])
out = root / "cut.mp4"
render(root, plan, out, root / "work", lambda c, **k: subprocess.run(c, check=True, capture_output=True))
info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(out)],
                                 capture_output=True, text=True).stdout)
video = next(s for s in info["streams"] if s["codec_type"] == "video")
print("cut video rate", video["r_frame_rate"], "time base", video["time_base"])
frames = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                                    "frame=pts_time", "-of", "json", str(out)], capture_output=True, text=True).stdout)["frames"]
times = np.array([float(f["pts_time"]) for f in frames])
raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(out), "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                     capture_output=True).stdout
lum = np.frombuffer(raw, np.uint8).reshape(len(times), -1).mean(axis=1)
flashes = times[lum > 128]
pcm = np.frombuffer(subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(out), "-ac", "1", "-ar", "48000", "-f",
                                    "f32le", "-"], capture_output=True).stdout, np.float32)
loud = np.nonzero(np.abs(pcm) > 0.3)[0]
onsets = loud[np.insert(np.diff(loud) > 4800, 0, True)] / 48000.0
print("flashes", len(flashes), "clicks", len(onsets))
k = min(len(flashes), len(onsets))
gap = (onsets[:k] - flashes[:k]) * 1000
print("click minus flash, ms: first", np.round(gap[:3], 3), "last", np.round(gap[-3:], 3),
      "min", round(float(gap.min()), 3), "max", round(float(gap.max()), 3))
print("frame duration ms", round(1000 * den / num, 3))
