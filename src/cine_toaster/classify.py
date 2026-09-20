from __future__ import annotations

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
    "assets": "assets",
    "cenas": "scenes",
    "characters": "characters",
    "docs": "documents",
    "edit": "edit",
    "edits": "edits",
    "locations": "locations",
    "renders": "renders",
    "scenes": "scenes",
    "sound": "sound",
    "story": "story",
    "world": "world",
    "workflows": "workflows",
}


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

    if lower_parts[0] in {"scenes", "cenas"}:
        if len(parts) == 2 and is_directory:
            return "scene_directory", None
        if "trabalho" in lower_parts or "shots" in lower_parts:
            return ("shots", None) if is_directory else ("shot_asset", media_type)
        if "_tomadas" in lower_parts or "_descartados" in lower_parts:
            return ("takes", None) if is_directory else ("take_asset", media_type)

    if path.name.lower() == "decupagem.yaml":
        return "scene_manifest", media_type
    if path.name.lower() == "project.yaml":
        return "project_manifest", media_type
    if path.name.lower() == "state.json":
        return "scene_state", media_type

    if path.suffix.lower() == ".fountain":
        return "screenplay_document", media_type
    if path.suffix.lower() == ".cube":
        return "lut", media_type

    if is_directory:
        return "directory", None
    if media_type:
        return media_type, media_type
    return "file", None
