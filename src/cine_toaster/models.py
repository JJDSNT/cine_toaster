"""The models that estimate signals (C8 step 3, CT-0081): which, at what revision, under what licence, where.

A model is never downloaded implicitly. `fetch` is the one act that reaches the network: it takes a model of
the catalog at its **pinned revision**, checks every weight file against the hash the catalog pins (the
hub's own content address), and keeps it under the models directory with a `model.json` of what was taken
(revision, licence, each file's hash). Estimating reads that directory only (`HF_HUB_OFFLINE`); a model not
fetched is refused with the command that fetches it.

The catalog holds only what ADR 0011 allows (Apache-2.0 here). Depth Anything V2's Base, Large and Giant are
CC-BY-NC-4.0 and named in `EXCLUDED`, so asking for one says why rather than "unknown".

Models run in their own environment, `.venv-vision` (`make install-vision`) or `CINE_TOASTER_VISION_PYTHON`:
torch never enters Cine Toaster's own.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
import urllib.request
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from .errors import ValidationError

REPOSITORY_VISION_PYTHON = Path(__file__).resolve().parents[2] / ".venv-vision" / "bin" / "python"

#: What each model is, pinned: the hub repository and revision, the files taken (weights by their sha256, the
#: hub's LFS address), its licence, what it gives, and how it treats time.
MODELS: dict[str, dict[str, Any]] = {
    "depth-anything-v2-small": {
        "task": "depth", "kind": "depth_relative", "time": "frame by frame: each frame estimated alone",
        "repo": "depth-anything/Depth-Anything-V2-Small-hf", "revision": "5426e4f0f36572d16453bbda7a8389317b1bef99",
        "files": {"config.json": None, "preprocessor_config.json": None,
                  "model.safetensors": "3152477ce0d8d6978d76b995120de97cb5b928701fd0f817769f59e249a16b70"},
        "licence": "Apache-2.0", "runner": "depth_anything_v2",
        # Affine-invariant inverse depth: larger is nearer, its scale and shift unknown.
        "depth": {"quantity": "inverse_z", "near_is_small": False, "scale": "unknown: affine (scale and shift)"},
    },
    "video-depth-anything-small": {
        "task": "depth", "kind": "depth_relative",
        "time": "a sequence: windows of 32 frames overlapping by 10, each aligned to the last by scale and "
                "shift on shared key frames -- estimated together, frame i of the result is frame i of the "
                "stretch; a part re-estimated alone is not the same result",
        "repo": "depth-anything/Video-Depth-Anything-Small", "revision": "256875362cff76724b920335dfb4b29dd611f66e",
        "files": {"video_depth_anything_vits.pth": "13379300b739e659f076a59d52e9801bd8d38c541a7e71f73bbca4dcfb013609"},
        # Its model code is not on the hub: the authors' repository at a pinned commit (Apache-2.0).
        "code": {"repo": "DepthAnything/Video-Depth-Anything", "commit": "4f5ae23172ba60fd7bc11ef671cca678842c7072",
                 "paths": ["video_depth_anything/", "utils/util.py", "utils/__init__.py", "LICENSE"]},
        "licence": "Apache-2.0", "runner": "video_depth_anything",
        "depth": {"quantity": "inverse_z", "near_is_small": False, "scale": "unknown: affine (scale and shift)"},
    },
    "sam2.1-hiera-tiny": {
        "task": "segmentation", "kind": "segmentation",
        "time": "a sequence: objects prompted on a frame are followed through the stretch with the model's "
                "memory of earlier frames; a label is one object, the same in every frame",
        "repo": "facebook/sam2.1-hiera-tiny", "revision": "de431c4043854a71d8101e17995dfe596bf101a5",
        "files": {"config.json": None, "preprocessor_config.json": None, "processor_config.json": None,
                  "video_preprocessor_config.json": None,
                  "model.safetensors": "48c14467e5cf9e51870511feb72c89688e82dd74523142c0538b663e193ac2a7"},
        "licence": "Apache-2.0", "runner": "sam2_video",
    },
}

#: Asked for by name, refused with the reason (ADR 0011).
EXCLUDED = {name: "CC-BY-NC-4.0: not for a tool that may be used commercially (ADR 0011); "
                  "depth-anything-v2-small is Apache-2.0"
            for name in ("depth-anything-v2-base", "depth-anything-v2-large", "depth-anything-v2-giant")}


def models_directory() -> Path:
    configured = os.environ.get("CINE_TOASTER_MODELS", "").strip()
    return Path(configured).expanduser() if configured else Path.home() / ".local" / "share" / "cine-toaster" / "models"


def entry(name: str) -> dict[str, Any]:
    if name in EXCLUDED:
        raise ValidationError(f"{name} is not used: {EXCLUDED[name]}")
    if name not in MODELS:
        raise ValidationError(f"There is no model {name!r}; the catalog has {', '.join(sorted(MODELS))}")
    return MODELS[name]


def vision_python() -> Path | None:
    """The interpreter that holds the models' libraries, when there is one."""

    configured = os.environ.get("CINE_TOASTER_VISION_PYTHON", "").strip()
    candidate = Path(configured).expanduser() if configured else REPOSITORY_VISION_PYTHON
    return candidate if candidate.is_file() and os.access(candidate, os.X_OK) else None


def environment_stamp(python: Path) -> tuple:
    """What changes when an environment is installed into: its packages' folders' times. A probe of it is
    asked again only then -- importing torch takes seconds, and the doctor asks often."""

    folders = sorted(Path(python).resolve().parent.parent.glob("lib/python*/site-packages"))
    return (str(python), *(folder.stat().st_mtime_ns for folder in folders))


@lru_cache(maxsize=8)
def _probe(stamp: tuple, modules: str) -> int:
    return subprocess.run([stamp[0], "-c", f"import {modules}"], capture_output=True, text=True,
                          timeout=180).returncode


def vision_unavailable_reason() -> str:
    python = vision_python()
    if python is None:
        return "no vision environment (make install-vision, or set CINE_TOASTER_VISION_PYTHON)"
    if _probe(environment_stamp(python), "torch, transformers, torchvision, cv2, einops"):
        return f"{python} lacks torch, transformers, torchvision, OpenCV or einops (make install-vision)"
    return ""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def model_directory(name: str) -> Path:
    model = entry(name)
    return models_directory() / name / model["revision"]


def installed(name: str) -> dict[str, Any] | None:
    """What was fetched of a model at its pinned revision (`model.json`), or None."""

    path = model_directory(name) / "model.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def require(name: str) -> dict[str, Any]:
    """A model ready to run: fetched at the catalog's revision, every file still the one fetched. Refused with
    the command otherwise -- never fetched here."""

    model = entry(name)
    made = installed(name)
    if made is None:
        raise ValidationError(f"The model {name} is not here: `toast models fetch {name}` (about "
                              f"{_size_hint(model)}; nothing is downloaded without it)")
    folder = model_directory(name)
    for relative, expected in made["files"].items():
        path = folder / relative
        if not path.is_file() or _sha256(path) != expected:
            raise ValidationError(f"The model {name}'s {relative} is not the file fetched: `toast models fetch "
                                  f"{name} --again`")
    return {**model, "name": name, "directory": str(folder), "installed": made}


def _size_hint(model: dict[str, Any]) -> str:
    return {"depth_anything_v2": "100 MB", "video_depth_anything": "120 MB", "sam2_video": "160 MB"}[model["runner"]]


def _download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310 -- a pinned https URL of the catalog
        return response.read()


def fetch(name: str, *, again: bool = False, download: Callable[[str], bytes] | None = None) -> dict[str, Any]:
    """Take a model of the catalog at its pinned revision -- the one act that downloads. Every weight file is
    checked against the catalog's hash; a mismatch keeps nothing."""

    model = entry(name)
    download = download or _download
    folder = model_directory(name)
    if installed(name) and not again:
        return {"model": name, "directory": str(folder), "fetched": False}
    staged = folder.with_name(f".{folder.name}.part")
    shutil.rmtree(staged, ignore_errors=True)
    staged.mkdir(parents=True)
    files: dict[str, str] = {}
    for relative, expected in model["files"].items():
        data = download(f"https://huggingface.co/{model['repo']}/resolve/{model['revision']}/{relative}")
        found = hashlib.sha256(data).hexdigest()
        if expected and found != expected:
            shutil.rmtree(staged, ignore_errors=True)
            raise ValidationError(f"{name}'s {relative} is not the file the catalog pins ({found[:12]}, not "
                                  f"{expected[:12]}): nothing kept")
        (staged / relative).write_bytes(data)
        files[relative] = found
    code = model.get("code")
    if code:
        archive = download(f"https://codeload.github.com/{code['repo']}/tar.gz/{code['commit']}")
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
            for member in tar.getmembers():
                inner = member.name.split("/", 1)[1] if "/" in member.name else ""
                if not member.isfile() or not any(inner == path or (path.endswith("/") and inner.startswith(path))
                                                  for path in code["paths"]):
                    continue
                target = staged / "code" / inner
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(tar.extractfile(member).read())
                files[f"code/{inner}"] = _sha256(target)
        (staged / "code" / "utils" / "__init__.py").touch()
        files["code/utils/__init__.py"] = _sha256(staged / "code" / "utils" / "__init__.py")
    record = {"model": name, "repo": model["repo"], "revision": model["revision"], "licence": model["licence"],
              **({"code": {"repo": code["repo"], "commit": code["commit"]}} if code else {}),
              "files": files, "fetched_at": datetime.now(UTC).isoformat()}
    (staged / "model.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
    if folder.exists():
        shutil.rmtree(folder)
    staged.replace(folder)
    return {"model": name, "directory": str(folder), "fetched": True, "files": len(files)}


def describe() -> list[dict[str, Any]]:
    """The catalog as `toast models list` shows it: each model, what it gives, and whether it is here."""

    return [{"model": name, "task": model["task"], "kind": model["kind"], "licence": model["licence"],
             "revision": model["revision"][:12], "fetched": installed(name) is not None, "time": model["time"]}
            for name, model in MODELS.items()]
