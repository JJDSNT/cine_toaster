from __future__ import annotations

import re
from pathlib import PurePosixPath


IMAGE_EXTENSIONS = {
    ".avif",
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}
VIDEO_EXTENSIONS = {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".webm"}
AUDIO_EXTENSIONS = {".aac", ".aiff", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav"}
TEXT_EXTENSIONS = {
    ".ass",
    ".csv",
    ".fountain",
    ".json",
    ".md",
    ".srt",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
DOCUMENT_EXTENSIONS = {".epub", ".fdx", ".odt", ".pdf"}

CATEGORY_KINDS = {
    "arquivo": "archive",
    "assets": "assets",
    "cenas": "scenes",
    "cenarios": "locations",
    "docs": "documents",
    "edits": "edits",
    "elenco": "cast",
    "estetica": "visual_style",
    "livro": "source_material",
    "renders": "renders",
    "roteiro": "screenplay",
    "sequencias": "sequences",
    "sons": "sound_library",
    "workflows": "workflows",
}

SCENE_NUMBER = re.compile(r"^\d+(?:-\d+)[A-Za-z]?(?:[-_].*)?$")
SHOT_STILL = re.compile(r"^p\d+[a-z]?(?:[-_].*)?$", re.IGNORECASE)
SHOT_CLIP = re.compile(r"^c\d+[a-z]?(?:[-_].*)?$", re.IGNORECASE)
TAKE_NAME = re.compile(r"^c\d+[a-z]?-t\d+(?:[-_].*)?$", re.IGNORECASE)
SCENE_VERSION = re.compile(r"^cena-.+-v\d+$", re.IGNORECASE)


def media_type_for(path: PurePosixPath) -> str | None:
    extension = path.suffix.lower()
    if extension in IMAGE_EXTENSIONS:
        return "image"
    if extension in VIDEO_EXTENSIONS:
        return "video"
    if extension in AUDIO_EXTENSIONS:
        return "audio"
    if extension in TEXT_EXTENSIONS:
        return "text"
    if extension in DOCUMENT_EXTENSIONS:
        return "document"
    return None


def classify(relative_path: str, *, is_directory: bool) -> tuple[str, str | None]:
    """Classify a path without making it part of the canonical project model.

    These labels are adapter hints for navigation. They can evolve independently
    from the files and do not mutate the source project.
    """

    if not relative_path:
        return "project", None

    path = PurePosixPath(relative_path)
    parts = path.parts
    lower_parts = tuple(part.lower() for part in parts)
    media_type = None if is_directory else media_type_for(path)

    if len(parts) == 1 and is_directory:
        return CATEGORY_KINDS.get(lower_parts[0], "directory"), None

    if lower_parts[0] == "cenas":
        if len(parts) == 2 and is_directory and SCENE_NUMBER.match(parts[1]):
            return "scene", None

        if "_tomadas" in lower_parts:
            if is_directory:
                return "takes", None
            if TAKE_NAME.match(path.stem):
                return "take", media_type

        if "_descartados" in lower_parts:
            return ("rejected", None) if is_directory else ("rejected_asset", media_type)

        if "versoes" in lower_parts:
            if is_directory:
                return "versions", None
            if media_type == "video" and SCENE_VERSION.match(path.stem):
                return "scene_version", media_type
            if path.name.lower().startswith("decupagem-v"):
                return "specification_version", media_type
            if path.name.lower() == "versoes.md":
                return "version_history", media_type

        if len(parts) == 3 and is_directory:
            return "scene_variant", None

        if path.name.lower() == "decupagem.yaml":
            return "scene_specification", media_type
        if path.name.lower().startswith("revisao-") and path.suffix.lower() == ".pdf":
            return "review_document", media_type
        if media_type == "video" and path.name.lower().startswith("cena-"):
            return "scene_render", media_type
        if path.name.lower() == "contato.png":
            return "contact_sheet", media_type
        if SHOT_STILL.match(path.stem) and media_type == "image":
            return "shot_still", media_type
        if SHOT_CLIP.match(path.stem) and media_type == "video":
            return "shot_clip", media_type
        if SHOT_CLIP.match(path.stem) and media_type == "audio":
            return "shot_audio", media_type

    if path.suffix.lower() == ".fountain":
        return "screenplay_document", media_type
    if path.name.upper() == "FICHA.MD":
        return "profile", media_type
    if path.name.upper() == "MANIFESTO.CSV":
        return "provenance_manifest", media_type
    if path.suffix.lower() == ".cube":
        return "lut", media_type

    if is_directory:
        return "directory", None
    if media_type:
        return media_type, media_type
    return "file", None

