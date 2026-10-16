"""Runs in the vision environment (`.venv-vision`), never in Cine Toaster's own: a model over frames.

    python vision_worker.py spec.json

The spec names the runner, the model's fetched directory, the frames (`frames.npy`: (count, height, width, 3)
uint8 sRGB, the medium's pixels), the parameters and the output folder. Written there:

- `result.npy`: (count, height, width) -- float32 for a depth, int32 labels for a segmentation;
- `alpha.npy`, for a segmentation: (count, objects, height, width) float32, each object's own probability (its
  mask logit's sigmoid), a soft matte of it -- below half an 8-bit step 0, above it from 1, 1;
- `meta.json`: what ran -- Python, torch, transformers, the device, threads, dtype, the determinism asked
  for, the model's own input size, how its output was brought to the medium's size, and what the model
  declared of itself (SAM 2's object scores). Nothing measured: measuring is the adapter's.

Offline by construction: the hub is told so before anything is imported, and models load from their folder.
"""

import json
import os
import sys
import time
import types
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TQDM_DISABLE"] = "1"

import numpy as np  # noqa: E402
import torch  # noqa: E402
import torch.nn.functional as F  # noqa: E402
import transformers  # noqa: E402

transformers.logging.set_verbosity_error()
transformers.logging.disable_progress_bar()

spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
out = Path(spec["output"])
out.mkdir(parents=True, exist_ok=True)
frames = np.load(spec["frames"])
count, height, width = frames.shape[:3]
parameters = spec.get("parameters") or {}
threads = int(spec.get("threads") or torch.get_num_threads())
torch.set_num_threads(threads)
torch.manual_seed(int(parameters.get("seed", 0)))
torch.use_deterministic_algorithms(True, warn_only=True)
model_dir = Path(spec["model_dir"])
meta = {"python": sys.version.split()[0], "torch": torch.__version__, "device": "cpu", "threads": threads,
        "dtype": "float32", "determinism": {"seed": int(parameters.get("seed", 0)),
                                            "deterministic_algorithms": True}}
started = time.monotonic()
extra = {}  # what a runner gives beside its result, saved as `<name>.npy`
#: A probability this near 0 or 1 is kept as 0 or 1: half an 8-bit step, so an object's soft matte ends.
SNAP = 1.0 / 512


def depth_anything_v2() -> np.ndarray:
    import transformers
    from PIL import Image
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation

    meta["transformers"] = transformers.__version__
    processor = AutoImageProcessor.from_pretrained(model_dir, local_files_only=True)
    model = AutoModelForDepthEstimation.from_pretrained(model_dir, local_files_only=True).eval()
    results = []
    for frame in frames:
        inputs = processor(images=Image.fromarray(frame), return_tensors="pt")
        meta["model_input"] = list(inputs["pixel_values"].shape[-2:])
        with torch.no_grad():
            predicted = model(**inputs).predicted_depth
        resized = F.interpolate(predicted[:, None], size=(height, width), mode="bilinear", align_corners=False)
        results.append(resized[0, 0].numpy().astype(np.float32))
    meta["resized"] = "bilinear, from the model's input size to the medium's"
    return np.stack(results)


def video_depth_anything() -> np.ndarray:
    # Its code imports two conveniences only for attribute access and a progress bar: stand-ins, so neither
    # (one LGPL) is installed.
    easydict = types.ModuleType("easydict")
    easydict.EasyDict = type("EasyDict", (dict,), {"__getattr__": dict.__getitem__})
    tqdm = types.ModuleType("tqdm")
    tqdm.tqdm = lambda iterable, *args, **kwargs: iterable
    sys.modules.setdefault("easydict", easydict)
    sys.modules.setdefault("tqdm", tqdm)
    sys.path.insert(0, str(model_dir / "code"))
    from video_depth_anything.video_depth import INFER_LEN, KEYFRAMES, OVERLAP, VideoDepthAnything

    model = VideoDepthAnything(encoder="vits", features=64, out_channels=[48, 96, 192, 384])
    model.load_state_dict(torch.load(model_dir / "video_depth_anything_vits.pth", map_location="cpu",
                                     weights_only=True), strict=True)
    model = model.eval()
    input_size = int(parameters.get("input_size", 518))
    depths, _ = model.infer_video_depth(frames, float(spec.get("fps", 24)), input_size=input_size, device="cpu",
                                        fp32=True)
    meta["model_input"] = input_size
    meta["temporal"] = {"window": INFER_LEN, "overlap": OVERLAP, "key_frames": KEYFRAMES,
                        "between_windows": "scale and shift fitted on the overlap's key frames",
                        "frames_together": int(count)}
    meta["resized"] = "bilinear (align corners), from the model's input size to the medium's, by its own code"
    return depths.astype(np.float32)


def sam2_video() -> np.ndarray:
    import transformers
    from transformers import Sam2VideoModel, Sam2VideoProcessor

    meta["transformers"] = transformers.__version__
    processor = Sam2VideoProcessor.from_pretrained(model_dir, local_files_only=True)
    model = Sam2VideoModel.from_pretrained(model_dir, local_files_only=True).eval()
    session = processor.init_video_session(video=list(frames), inference_device="cpu", dtype=torch.float32)
    objects = parameters["objects"]
    for item in objects:
        processor.add_inputs_to_inference_session(  # adds to the session in place
            inference_session=session, frame_idx=int(item.get("frame", 0)), obj_ids=int(item["label"]),
            **({"input_points": [[item["points"]]], "input_labels": [[item.get("point_labels") or
                                                                       [1] * len(item["points"])]]}
               if item.get("points") else {}),
            **({"input_boxes": [[item["box"]]]} if item.get("box") else {}))
        with torch.no_grad():  # each object seen on its frame as it is asked for, so following starts there
            model(inference_session=session, frame_idx=int(item.get("frame", 0)))
    logits = np.full((count, len(objects), height, width), -np.inf, np.float32)
    presence = np.zeros((count, len(objects)), np.float32)
    order = [int(item["label"]) for item in objects]
    first = min(int(item.get("frame", 0)) for item in objects)

    def collect(reverse: bool) -> None:
        with torch.no_grad():
            for output in model.propagate_in_video_iterator(session, start_frame_idx=first, reverse=reverse):
                masks = processor.post_process_masks([output.pred_masks], original_sizes=[[height, width]],
                                                     binarize=False)[0]
                for row, label in enumerate(output.object_ids):
                    index = order.index(int(label))
                    logits[output.frame_idx, index] = masks[row, 0].numpy()
                    if output.object_score_logits is not None:
                        presence[output.frame_idx, index] = float(torch.sigmoid(output.object_score_logits[row]).
                                                                  reshape(-1)[0])

    collect(False)
    if first > 0:
        collect(True)
    best = logits.argmax(axis=1)
    labels = np.where(logits.max(axis=1) > 0.0, np.asarray(order, np.int32)[best], 0).astype(np.int32)
    meta["overlaps"] = "a pixel claimed by several objects goes to the highest mask logit"
    meta["threshold"] = "mask logit > 0"
    with np.errstate(over="ignore"):
        alpha = (1.0 / (1.0 + np.exp(-logits))).astype(np.float32)  # -inf (not followed there) is 0
    alpha[alpha < SNAP] = 0.0
    alpha[alpha > 1.0 - SNAP] = 1.0
    extra["alpha"] = alpha
    meta["alpha"] = {"what": "each object's own probability: the sigmoid of its mask logit, at the medium's size",
                     "snapped": f"below {SNAP:.6f} to 0, above {1 - SNAP:.6f} to 1",
                     "overlaps": "kept: each object's alpha is its own, not resolved against the others"}
    meta["declared"] = {"what": "the model's object score (sigmoid), per object per frame",
                        "by_object": {str(label): presence[:, index].round(4).tolist()
                                      for index, label in enumerate(order)}}
    meta["resized"] = "the processor's post-processing, to the medium's size"
    return labels


RUNNERS = {"depth_anything_v2": depth_anything_v2, "video_depth_anything": video_depth_anything,
           "sam2_video": sam2_video}
result = RUNNERS[spec["runner"]]()
meta["seconds"] = round(time.monotonic() - started, 3)
np.save(out / "result.npy", result)
for name, data in extra.items():
    np.save(out / f"{name}.npy", data)
(out / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
