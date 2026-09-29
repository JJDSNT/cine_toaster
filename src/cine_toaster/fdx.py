"""Final Draft interchange (plan step 5, ADR 0014).

FDX is an interchange format, never production state:

- **import** turns an `.fdx` into a **new** Fountain file, which becomes the
  authored screenplay, and reports everything the conversion could not keep;
- **export** turns the authored Fountain into a derived `.fdx`, which is never
  edited in place and never read back as truth.

screenplay-tools' own FDX reader keeps only the first text run of a paragraph,
drops dual dialogue, turns a Shot into a scene heading and loses scene numbers,
so both directions are written here with the standard library. Its Fountain
parser still reads the Fountain side for export.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any
from xml.dom import minidom

_EMPHASIS = {"Bold": "**", "Italic": "*", "Underline": "_"}
_HEADING_START = re.compile(r"^(INT|EXT|EST|INT\./EXT|INT/EXT|I/E)[\s.]", re.IGNORECASE)
_KEPT_STYLES = set(_EMPHASIS)


@dataclass(slots=True)
class Loss:
    """Something in the source that the other side cannot hold."""

    what: str
    count: int
    detail: str = ""

    def public_dict(self) -> dict[str, Any]:
        return {"what": self.what, "count": self.count, "detail": self.detail}


@dataclass(slots=True)
class Conversion:
    text: str
    losses: list[Loss] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    elements: int = 0

    def report(self) -> str:
        lines = [f"{self.elements} element(s) converted."]
        lines += [f"  note: {note}" for note in self.notes]
        if not self.losses:
            lines.append("Nothing was lost.")
        for loss in self.losses:
            lines.append(f"  lost: {loss.what} ({loss.count})" + (f" -- {loss.detail}" if loss.detail else ""))
        return "\n".join(lines)


# --- import ----------------------------------------------------------------


def _runs(paragraph: ET.Element, lost_styles: dict[str, int], revised: list[int]) -> str:
    """A paragraph's text, with Final Draft's styled runs as Fountain emphasis."""

    out = []
    for run in paragraph.findall("Text"):
        text = "".join(run.itertext())
        if run.get("RevisionID") not in (None, "", "0"):
            revised[0] += 1
        styles = [style for style in (run.get("Style") or "").split("+") if style]
        for style in styles:
            if style not in _KEPT_STYLES:
                lost_styles[style] = lost_styles.get(style, 0) + 1
        core = text.strip()
        if not core or not styles:
            out.append(text)
            continue
        marks = "".join(_EMPHASIS[style] for style in ("Underline", "Bold", "Italic") if style in styles)
        closing = marks[::-1]
        lead = text[: len(text) - len(text.lstrip())]
        trail = text[len(text.rstrip()):]
        out.append(f"{lead}{marks}{core}{closing}{trail}")
    return "".join(out)


def _title_page(root: ET.Element) -> tuple[list[str], list[str]]:
    """Final Draft's title page is laid out, not labelled: read it by position.

    Centred lines give the title, then a credit ("Written by") and the
    authors. Left-aligned lines at the bottom are contact details, except a
    copyright line.
    """

    content = root.find("TitlePage/Content")
    if content is None:
        return [], []
    centred, left = [], []
    for paragraph in content.findall("Paragraph"):
        text = "".join("".join(run.itertext()) for run in paragraph.findall("Text")).strip()
        if not text:
            continue
        (centred if paragraph.get("Alignment") == "Center" else left).append(text)
    entries, notes = [], []
    if centred:
        credit_at = next((i for i, line in enumerate(centred) if re.fullmatch(r"(written\s+)?by", line, re.IGNORECASE)), None)
        title = centred[: credit_at if credit_at is not None else 1]
        entries.append("Title: " + " ".join(title))
        if credit_at is not None:
            entries.append(f"Credit: {centred[credit_at]}")
            authors = centred[credit_at + 1:]
            if authors:
                entries.append("Author: " + " & ".join(authors))
        elif len(centred) > 1:
            notes.append("title page: centred lines after the title were kept as the title's authors")
            entries.append("Author: " + " & ".join(centred[1:]))
    contact = []
    for line in left:
        if re.search(r"copyright|\(c\)|©", line, re.IGNORECASE):
            entries.append(f"Copyright: {line}")
        else:
            contact.extend(line.splitlines())
    if contact:
        entries.append("Contact:\n" + "\n".join(f"    {line}" for line in contact))
    if entries:
        notes.append("title page read from its layout (centred title and credit, left contact)")
    return entries, notes


def _count(root: ET.Element, path: str) -> int:
    node = root.find(path)
    return 0 if node is None else len(list(node))


def import_fdx(xml_text: str) -> Conversion:
    """An `.fdx` as Fountain text, with a report of what could not be kept."""

    try:
        root = ET.fromstring(xml_text.lstrip("﻿").encode("utf-8"))
    except ET.ParseError as error:
        raise ValueError(f"Not a readable FDX file: {error}") from error
    if root.tag != "FinalDraft":
        raise ValueError("Not an FDX file: the root element is not FinalDraft")
    content = root.find("Content")
    if content is None:
        raise ValueError("The FDX file has no Content")

    lost_styles: dict[str, int] = {}
    revised = [0]
    counts = {"shot": 0, "other": 0, "scene_properties": 0}
    other_types: set[str] = set()
    blocks: list[tuple[str, str]] = []
    elements = 0
    title, notes = _title_page(root)

    def emit(paragraph: ET.Element, dual: bool, dual_seen: list[int]) -> None:
        nonlocal elements
        kind = paragraph.get("Type") or ""
        text = _runs(paragraph, lost_styles, revised).strip()
        if paragraph.find("SceneProperties") is not None:
            properties = paragraph.find("SceneProperties").attrib
            if any(properties.get(key) for key in ("Title", "Color", "Summary")) or paragraph.find("SceneProperties/Summary") is not None:
                counts["scene_properties"] += 1
        if not text:
            return
        elements += 1
        if paragraph.get("StartsNewPage") == "Yes":
            blocks.append(("page", "==="))
        if kind in ("Scene Heading", "Scene Heading (Top of Page)"):
            number = paragraph.get("Number")
            line = text if _HEADING_START.match(text) else f".{text}"
            blocks.append(("heading", line + (f" #{number}#" if number else "")))
        elif kind == "Character":
            dual_seen[0] += 1
            name = text if text == text.upper() else f"@{text}"
            if dual and dual_seen[0] == 2:
                name += " ^"
            blocks.append(("cue", name))
        elif kind == "Parenthetical":
            blocks.append(("speech", text if text.startswith("(") else f"({text})"))
        elif kind == "Dialogue":
            blocks.append(("speech", text))
        elif kind == "Transition":
            upper = text.upper() == text
            blocks.append(("transition", text if upper and text.endswith("TO:") else f"> {text}"))
        else:
            if kind == "Shot":
                counts["shot"] += 1
            elif kind not in ("Action", "General", ""):
                counts["other"] += 1
                other_types.add(kind)
            # A line that Fountain would read as something else is forced to action.
            risky = text == text.upper() and (text.endswith("TO:") or _HEADING_START.match(text) or len(text.split()) <= 4)
            blocks.append(("action", f"!{text}" if risky else text))

    for paragraph in content.findall("Paragraph"):
        dual = paragraph.find("DualDialogue")
        if dual is not None:
            seen = [0]
            for inner in dual.findall("Paragraph"):
                emit(inner, True, seen)
            continue
        emit(paragraph, False, [0])

    # Fountain wants a blank line around every element except inside a speech.
    lines: list[str] = []
    previous = ""
    for kind, block in blocks:
        inside_speech = kind == "speech" and previous in ("cue", "speech")
        if lines and not inside_speech:
            lines.append("")
        lines.append(block)
        previous = kind
    body = "\n".join(lines).strip() + "\n"
    header = "\n".join(title) + "\n\n" if title else ""

    result = Conversion(text=header + body, notes=notes, elements=elements)
    losses = [
        ("revision marks", revised[0], "Fountain has no revision sets; the current text is kept"),
        ("revision sets", _count(root, "Revisions") if revised[0] else 0, "colours and names of the revision sets those marks belong to"),
        ("script notes", _count(root, "ScriptNotes"), "Final Draft notes are not converted to [[notes]]"),
        ("tags", _count(root, "TagData/Tags"), "production tagging (props, wardrobe…); Cine Toaster keeps these as records"),
        ("scene properties", counts["scene_properties"], "scene titles, colours and summaries"),
        ("shots", counts["shot"], "Fountain has no shot element; written as forced action"),
        ("other element types", counts["other"], ", ".join(sorted(other_types))),
        ("locked pages", _count(root, "LockedPages"), "page locks and A-pages"),
        ("alternate lines", _count(root, "AltCollection"), "Final Draft's alts"),
        ("images", _count(root, "Images"), ""),
        ("outlines", _count(root, "Outlines"), "Final Draft's outline elements"),
    ]
    for style, count in sorted(lost_styles.items()):
        losses.append((f"text style {style}", count, "only bold, italic and underline exist in Fountain"))
    result.losses = [Loss(what, count, detail) for what, count, detail in losses if count]
    return result


# --- export ----------------------------------------------------------------

_MARK = re.compile(r"(\*\*\*|\*\*|\*|_)(?=\S)(.+?)(?<=\S)\1")


def _styled_runs(parent: ET.Element, text: str) -> None:
    """Fountain emphasis as Final Draft styled runs."""

    position = 0
    for match in _MARK.finditer(text):
        if match.start() > position:
            ET.SubElement(parent, "Text").text = text[position:match.start()]
        style = {"***": "Bold+Italic", "**": "Bold", "*": "Italic", "_": "Underline"}[match.group(1)]
        inner = match.group(2)
        run = ET.SubElement(parent, "Text", Style=style)
        run.text = _MARK.sub(r"\2", inner)
        position = match.end()
    if position < len(text) or not len(parent):
        ET.SubElement(parent, "Text").text = text[position:]


def export_fdx(fountain_text: str) -> Conversion:
    """Authored Fountain as a derived `.fdx`, with what Final Draft will not get."""

    from screenplay_tools.fountain.parser import Parser
    from screenplay_tools.screenplay import ElementType

    parser = Parser()
    parser.add_text(fountain_text)
    parser.finalize()
    script = parser.script

    root = ET.Element("FinalDraft", DocumentType="Script", Template="No", Version="5")
    content = ET.SubElement(root, "Content")
    dropped: dict[str, int] = {}
    elements = 0
    dual_open: ET.Element | None = None
    pending_page = False

    def paragraph(kind: str, text: str, parent: ET.Element | None = None, **attributes: str) -> ET.Element:
        nonlocal elements, pending_page
        node = ET.SubElement(parent if parent is not None else content, "Paragraph", Type=kind, **attributes)
        if pending_page:
            node.set("StartsNewPage", "Yes")
            pending_page = False
        _styled_runs(node, text)
        elements += 1
        return node

    speech: list[tuple[str, str]] = []
    items = list(script.elements)
    index = 0
    while index < len(items):
        element = items[index]
        kind = element.type
        if kind == ElementType.CHARACTER:
            # A speech is its cue and what follows it; a dual speech pairs with the previous one.
            block = [element]
            index += 1
            while index < len(items) and items[index].type in (ElementType.DIALOGUE, ElementType.PARENTHETICAL, ElementType.LYRIC):
                block.append(items[index])
                index += 1
            parent = content
            if element.is_dual_dialogue and speech:
                previous_nodes = speech.pop()
                wrapper = ET.Element("Paragraph")
                dual = ET.SubElement(wrapper, "DualDialogue")
                for node in previous_nodes:
                    content.remove(node)
                    dual.append(node)
                content.append(wrapper)
                parent = dual
            nodes = []
            name = element.name + (f" ({element.extension})" if element.extension else "")
            nodes.append(paragraph("Character", name, parent))
            for part in block[1:]:
                if part.type == ElementType.PARENTHETICAL:
                    text = part.text if part.text.startswith("(") else f"({part.text})"
                    nodes.append(paragraph("Parenthetical", text, parent))
                else:
                    nodes.append(paragraph("Dialogue", part.text, parent))
            speech = [nodes] if parent is content else []
            continue
        speech = []
        if kind == ElementType.HEADING:
            attributes = {"Number": str(element.scene_number)} if getattr(element, "scene_number", None) else {}
            paragraph("Scene Heading", element.text, **attributes)
        elif kind == ElementType.ACTION:
            for chunk in re.split(r"\n\s*\n", element.text):
                if chunk.strip():
                    node = paragraph("Action", chunk.strip())
                    if getattr(element, "centered", False):
                        node.set("Alignment", "Center")
        elif kind == ElementType.TRANSITION:
            paragraph("Transition", element.text)
        elif kind == ElementType.PAGEBREAK:
            pending_page = True
        else:
            name = kind.name.lower()
            dropped[name] = dropped.get(name, 0) + 1
        index += 1

    entries = {entry.key.lower(): entry.text for entry in script.titleEntries}
    if entries:
        page = ET.SubElement(ET.SubElement(root, "TitlePage"), "Content")
        for key in ("title", "credit", "author", "authors", "source"):
            if entries.get(key):
                for line in entries[key].splitlines():
                    node = ET.SubElement(page, "Paragraph", Alignment="Center")
                    ET.SubElement(node, "Text").text = line.strip()
        for key in ("draft date", "copyright", "contact", "notes"):
            if entries.get(key):
                for line in entries[key].splitlines():
                    node = ET.SubElement(page, "Paragraph", Alignment="Left")
                    ET.SubElement(node, "Text").text = line.strip()

    xml = minidom.parseString(ET.tostring(root, encoding="unicode")).toprettyxml(indent="  ", encoding="UTF-8")
    result = Conversion(text=xml.decode("utf-8"), elements=elements)
    details = {"note": "Fountain [[notes]]", "boneyard": "/* boneyard */ text", "section": "# sections",
               "synopsis": "= synopses", "lyric": "lyrics outside a speech"}
    result.losses = [Loss(details.get(name, name), count) for name, count in sorted(dropped.items())]
    if script.notes:
        result.losses.append(Loss("Fountain [[notes]]", len(script.notes)))
    result.notes.append("element formatting and page layout are left to Final Draft's defaults")
    return result
