"""Searching a source for music (CT-0064): a category filter must not hide what a source does not categorise."""

from __future__ import annotations

import unittest
import urllib.parse
from unittest import mock

from cine_toaster import sound_sources


def item(identifier: str, category: str | None, seconds: float) -> dict:
    return {"id": identifier, "title": identifier, "creator": "someone", "source": "freesound", "category": category,
            "duration": int(seconds * 1000), "license": "cc0", "license_version": "1.0", "foreign_landing_url": ""}


class OpenverseSearchTests(unittest.TestCase):
    def search(self, catalogued: list[dict], everything: list[dict], **options) -> tuple[list[str], list[dict]]:
        asked: list[dict] = []

        def answer(url: str) -> dict:
            query = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
            asked.append(query)
            return {"results": catalogued if query.get("category") == "music" else everything}

        with mock.patch.object(sound_sources, "_get_json", answer):
            return [found["id"] for found in sound_sources.openverse_search("synthwave", 3, **options)], asked

    def test_music_with_no_category_is_found_and_short_sounds_are_not(self) -> None:
        found, asked = self.search([], [item("stab", None, 4), item("track", None, 197), item("word", "pronunciation", 60),
                                        item("loop", None, 40)])
        self.assertEqual(found, ["track", "loop"])
        self.assertEqual([query.get("category") for query in asked], ["music", None])

    def test_catalogued_music_comes_first_and_is_not_repeated(self) -> None:
        found, _ = self.search([item("jamendo", "music", 200)], [item("jamendo", "music", 200), item("track", None, 197)])
        self.assertEqual(found, ["jamendo", "track"])

    def test_enough_catalogued_music_asks_once_and_any_audio_asks_without_a_category(self) -> None:
        full = [item(name, "music", 200) for name in "abc"]
        self.assertEqual(len(self.search(full, [])[1]), 1)
        found, asked = self.search([], [item("stab", None, 4)], music=False)
        self.assertEqual((found, [query.get("category") for query in asked]), (["stab"], [None]))


if __name__ == "__main__":
    unittest.main()
