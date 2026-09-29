"""A transition's shader runs over real frames, as the preview runs it."""

from __future__ import annotations

import unittest

from cine_toaster.shader_render import ShaderTransition, gl_unavailable_reason
from cine_toaster.transitions import list_transitions

WIDTH, HEIGHT = 8, 4
RED = bytes([255, 0, 0]) * (WIDTH * HEIGHT)
BLUE = bytes([0, 0, 255]) * (WIDTH * HEIGHT)


@unittest.skipIf(gl_unavailable_reason(), "no GL context on this machine")
class ShaderTransitionTests(unittest.TestCase):
    def renderer(self, transition_id: str, **overrides) -> ShaderTransition:
        item = next(item for item in list_transitions() if item["id"] == transition_id)
        return ShaderTransition(item["asset_path"], item["params"], WIDTH, HEIGHT, overrides)

    def test_a_dissolve_blends_halfway(self) -> None:
        renderer = self.renderer("cross-dissolve")
        try:
            self.assertEqual(renderer.render(RED, BLUE, 0.0)[:3], bytes([255, 0, 0]))
            self.assertEqual(renderer.render(RED, BLUE, 1.0)[:3], bytes([0, 0, 255]))
            red, _, blue = renderer.render(RED, BLUE, 0.5)[:3]
            self.assertAlmostEqual(red, 128, delta=2)
            self.assertAlmostEqual(blue, 128, delta=2)
        finally:
            renderer.release()

    def test_declared_defaults_reach_the_shader(self) -> None:
        # Dip to black passes through its colour, black unless overridden.
        dark, light = self.renderer("dip-to-black"), self.renderer("dip-to-black", color=[1.0, 1.0, 1.0])
        try:
            self.assertLess(max(dark.render(RED, BLUE, 0.5)), 20)
            self.assertGreater(min(light.render(RED, BLUE, 0.5)), 200)
        finally:
            dark.release()
            light.release()

    def test_an_unknown_parameter_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            self.renderer("dip-to-black", nonsense=1.0)


if __name__ == "__main__":
    unittest.main()
