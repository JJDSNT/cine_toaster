"""Builds `colour-test.ttf`, the colour font the tests draw with (C6b stage C, CT-0078).

An OpenType font with a COLR (version 0) table and its CPAL palette: each of the
letters A, B and C is a square whose lower half is red, whose upper half is blue,
and with a yellow diamond in the middle -- three layers in three colours, so a
test can tell the font's colours from a text's single colour. Its outline (the
whole square) is what a reader without colour support would draw.

Made by this script with fontTools, which is needed only to remake the file:
    PYTHONPATH=<fontTools> python3 tests/fixtures/fonts/make_colour_font.py
"""

from __future__ import annotations

from pathlib import Path

from fontTools.colorLib.builder import buildCOLR, buildCPAL
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

EM, ADVANCE = 1000, 900
LETTERS = ("A", "B", "C")


def polygon(points: list[tuple[int, int]]):
    pen = TTGlyphPen(None)
    pen.moveTo(points[0])
    for point in points[1:]:
        pen.lineTo(point)
    pen.closePath()
    return pen.glyph()


def build(path: Path) -> None:
    square = [(50, 0), (50, 800), (850, 800), (850, 0)]
    shapes = {
        ".notdef": polygon(square), "space": TTGlyphPen(None).glyph(), "square": polygon(square),
        "lower": polygon([(50, 0), (50, 400), (850, 400), (850, 0)]),
        "upper": polygon([(50, 400), (50, 800), (850, 800), (850, 400)]),
        "diamond": polygon([(450, 150), (200, 400), (450, 650), (700, 400)]),
    }
    names = [".notdef", "space", *LETTERS, "lower", "upper", "diamond"]
    glyphs = {name: shapes.get(name, shapes["square"]) for name in names}
    builder = FontBuilder(EM, isTTF=True)
    builder.setupGlyphOrder(names)
    builder.setupCharacterMap({0x20: "space", **{ord(letter): letter for letter in LETTERS}})
    builder.setupGlyf(glyphs)
    # A glyph's left side bearing is where its outline starts: TrueType places the outline by it.
    bearing = {name: min((x for x, _ in glyph.coordinates), default=0) for name, glyph in glyphs.items()}
    builder.setupHorizontalMetrics({name: (ADVANCE if name != "space" else 500, bearing[name]) for name in names})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({"familyName": "Cine Toaster Colour Test", "styleName": "Regular"})
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    builder.setupPost()
    builder.font["COLR"] = buildCOLR({letter: [("lower", 0), ("upper", 1), ("diamond", 2)] for letter in LETTERS})
    builder.font["CPAL"] = buildCPAL([[(1.0, 0.0, 0.0, 1.0), (0.0, 0.0, 1.0, 1.0), (1.0, 1.0, 0.0, 1.0)]])
    builder.save(str(path))


if __name__ == "__main__":
    build(Path(__file__).with_name("colour-test.ttf"))
