"""Run a transition's own GLSL shader over real frames.

The shaders follow the gl-transitions contract: `vec4 transition(vec2 uv)`,
reading `getFromColor`, `getToColor`, `progress` and `ratio`. The browser
preview wraps them in WebGL; this wraps them in desktop GL through ModernGL,
so the transition the film gets is the one that was previewed.

ModernGL is optional (the `gpu` extra). Without it, or without a GL context,
the build falls back to each item's declared FFmpeg stand-in.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_VERTEX = """#version 330
in vec2 position;
out vec2 vUv;
void main() {
  vUv = position * 0.5 + 0.5;
  gl_Position = vec4(position, 0.0, 1.0);
}
"""

_FRAGMENT_HEAD = """#version 330
#define texture2D texture
uniform sampler2D fromTexture;
uniform sampler2D toTexture;
uniform float progress;
uniform float ratio;
in vec2 vUv;
out vec4 fragColor;
vec4 getFromColor(vec2 uv) { return texture(fromTexture, uv); }
vec4 getToColor(vec2 uv) { return texture(toTexture, uv); }
"""


def gl_unavailable_reason() -> str | None:
    """Why shaders cannot run here, or None when they can."""

    try:
        import moderngl
    except ImportError:
        return "ModernGL is not installed (uv sync --extra gpu, or pip install -e '.[gpu]')"
    try:
        context = moderngl.create_standalone_context()
    except Exception as error:  # the driver's message is the useful part
        return f"no GL context could be created: {error}"
    context.release()
    return None


class ShaderTransition:
    """One compiled transition, rendering RGB frames of a fixed size."""

    def __init__(self, shader: Path, params: list[dict[str, Any]], width: int, height: int,
                 overrides: dict[str, Any] | None = None) -> None:
        import moderngl

        self.width, self.height = width, height
        self.context = moderngl.create_standalone_context()
        source = shader.read_text(encoding="utf-8")
        self.program = self.context.program(
            vertex_shader=_VERTEX,
            fragment_shader=_FRAGMENT_HEAD + source + "\nvoid main() { fragColor = transition(vUv); }\n",
        )
        values = {param["name"]: param["default"] for param in params}
        unknown = set(overrides or {}) - set(values)
        if unknown:
            raise ValueError(f"{shader.stem} has no parameter(s) {', '.join(sorted(unknown))}")
        values.update(overrides or {})
        types = {param["name"]: param["type"] for param in params}
        for name, value in values.items():
            if name not in self.program:  # declared but optimised away by the compiler
                continue
            if types[name] == "bool":
                value = bool(value)
            elif isinstance(value, list):
                value = tuple(value)
            self.program[name].value = value
        if "ratio" in self.program:
            self.program["ratio"].value = width / height
        if "fromTexture" in self.program:
            self.program["fromTexture"].value = 0
        if "toTexture" in self.program:
            self.program["toTexture"].value = 1

        import struct

        quad = struct.pack("12f", -1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1)
        self.vao = self.context.vertex_array(
            self.program, [(self.context.buffer(quad), "2f", "position")]
        )
        self.textures = [self.context.texture((width, height), 3) for _ in range(2)]
        for texture in self.textures:
            texture.repeat_x = texture.repeat_y = False
        self.target = self.context.simple_framebuffer((width, height), components=3)

    def render(self, outgoing: bytes, incoming: bytes, progress: float) -> bytes:
        """Frames are packed RGB, bottom row first -- GL's own orientation."""

        # Standalone contexts share one "current" slot; claim ours first.
        with self.context:
            return self._render(outgoing, incoming, progress)

    def _render(self, outgoing: bytes, incoming: bytes, progress: float) -> bytes:
        self.textures[0].write(outgoing)
        self.textures[1].write(incoming)
        self.textures[0].use(0)
        self.textures[1].use(1)
        if "progress" in self.program:
            self.program["progress"].value = progress
        self.target.use()
        self.vao.render()
        return self.target.read(components=3, alignment=1)

    def release(self) -> None:
        self.context.release()
