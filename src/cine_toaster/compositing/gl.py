"""A GL renderer of SPEC-0012 graphs (ADR 0022 §5, §9): the same graph, drawn by shaders, checked against the reference.

The reference defines the right result; this one is fast. It draws in float
textures (RGBA32F pictures, R32F mattes and signals), linear and premultiplied
as the colour contract says, and takes its geometry (a transform's corners, a
surface's mesh) and its curves from the very functions the reference uses, so
only the drawing differs.

It implements a subset (`IMPLEMENTED`); a graph with anything else is refused
by name and goes to the reference. Time operations are not in it yet: each
frame here is made from that frame's inputs alone.

On this machine GL is Mesa's llvmpipe (or, with `GALLIUM_DRIVER=d3d12`, the
Intel GPU through Windows): measured, a 1080p float pass is 1.5 ms on llvmpipe,
5.4 ms on the GPU, and a read back to the CPU 8-18 ms.
"""

from __future__ import annotations

import struct
from typing import Any, Callable

import numpy as np

from ..errors import ValidationError
from .reference import LINEAR, REC709, Clip, _Held, curve_factory, read
from .schema import validate
from .semantics import blur_kernel, threshold_spread
from .semantics import default as semantic_default

IMPLEMENTED = {
    "generate.source", "generate.solid", "generate.gradient",
    "signal.luminance", "signal.luma", "signal.channel",
    "matte.from_signal", "matte.threshold", "matte.combine", "matte.key",
    "merge.over", "merge.mix", "merge.blend", "merge.porter_duff",
    "warp.transform", "warp.corner_pin", "warp.surface",
    "colour.grade", "colour.invert",
    "filter.blur",
    "curve.progress", "curve.keys", "curve.map", "curve.combine", "curve.noise", "curve.beats",
    "opaque.gl",
}

# A gl-transitions shader, run inside this renderer as an opaque node (SPEC-0012 §3; CT-0072, B1). The
# shaders were written for display-encoded pictures with uv (0, 0) at the bottom left: the picture is
# encoded and turned for them, and their result decoded and turned back, so each looks as its author made it.
_OPAQUE_HEAD = """#version 330
in vec2 uv;
out vec4 result;
uniform sampler2D fromTexture;
uniform sampler2D toTexture;
uniform float progress;
uniform float ratio;
float encode1(float c) { c = max(c, 0.0); return c <= 0.0031308 ? c * 12.92 : 1.055 * pow(c, 1.0 / 2.4) - 0.055; }
float decode1(float c) { return c <= 0.04045 ? c / 12.92 : pow((c + 0.055) / 1.055, 2.4); }
vec4 shown(sampler2D picture, vec2 p) {
  vec4 c = texture(picture, vec2(p.x, 1.0 - p.y));
  vec3 s = c.a > 1e-6 ? c.rgb / c.a : vec3(0.0);
  return vec4(encode1(s.r), encode1(s.g), encode1(s.b), c.a);
}
vec4 getFromColor(vec2 p) { return shown(fromTexture, p); }
vec4 getToColor(vec2 p) { return shown(toTexture, p); }
// A shader's own textures (a luma map) are read as it expects: display-encoded, bottom row first.
#define texture2D(sampler, p) shown(sampler, p)
"""
_OPAQUE_FOOT = """
void main() {
  vec4 c = transition(vec2(uv.x, 1.0 - uv.y));
  vec3 linear = vec3(decode1(c.r), decode1(c.g), decode1(c.b));
  result = vec4(linear * c.a, c.a);
}
"""

_VERTEX = """#version 330
in vec2 position;
out vec2 uv;
void main() { uv = position * 0.5 + 0.5; gl_Position = vec4(position, 0.0, 1.0); }
"""

# Pictures are stored top row first, as NumPy holds them: uv.y = 0 is the top.
_HEAD = """#version 330
in vec2 uv;
out vec4 result;
const vec3 REC709 = vec3(0.2126, 0.7152, 0.0722);
vec3 straight(vec4 p) { return p.a > 1e-6 ? p.rgb / p.a : vec3(0.0); }
float encode1(float c) { c = max(c, 0.0); return c <= 0.0031308 ? c * 12.92 : 1.055 * pow(c, 1.0 / 2.4) - 0.055; }
vec3 encode(vec3 c) { return vec3(encode1(c.r), encode1(c.g), encode1(c.b)); }
"""

_SHADERS = {
    "solid": "uniform vec4 colour; void main() { result = colour; }",
    "gradient": """uniform vec4 c0; uniform vec4 c1; uniform int radial; uniform float angle; uniform vec2 size;
        void main() {
          vec2 p = uv; float x;
          if (radial == 1) x = length(p - 0.5) / length(vec2(0.5));
          else x = (p.x - 0.5) * cos(angle) + (p.y - 0.5) * sin(angle) + 0.5;
          x = clamp(x, 0.0, 1.0); vec4 c = mix(c0, c1, x); result = vec4(c.rgb * c.a, c.a);
        }""",
    "luminance": """uniform sampler2D a; uniform vec3 weights; uniform int encoded;
        void main() { vec3 s = straight(texture(a, uv)); if (encoded == 1) s = encode(s);
                      result = vec4(dot(s, weights), 0.0, 0.0, 1.0); }""",
    "channel": """uniform sampler2D a; uniform int index;
        void main() { vec4 p = texture(a, uv); result = vec4(p[index], 0.0, 0.0, 1.0); }""",
    "from_signal": """uniform sampler2D a; uniform float low; uniform float high; uniform float gam; uniform int inv;
        void main() { float s = texture(a, uv).r; float m = pow(clamp((s - low) / max(high - low, 1e-9), 0.0, 1.0), gam);
                      result = vec4(inv == 1 ? 1.0 - m : m, 0.0, 0.0, 1.0); }""",
    "threshold": """uniform sampler2D a; uniform float progress; uniform float spread;
        void main() { float p = progress * (1.0 + 2.0 * spread) - spread;
                      result = vec4(clamp((p - texture(a, uv).r) / (2.0 * spread) + 0.5, 0.0, 1.0), 0.0, 0.0, 1.0); }""",
    "combine": """uniform sampler2D a; uniform sampler2D b; uniform int how;
        void main() { float x = texture(a, uv).r, y = texture(b, uv).r; float m;
                      if (how == 0) m = max(x, y); else if (how == 1) m = min(x, y);
                      else if (how == 2) m = clamp(x - y, 0.0, 1.0); else m = x * y;
                      result = vec4(m, 0.0, 0.0, 1.0); }""",
    "key": """uniform sampler2D a; uniform float low; uniform float high; uniform int inv; uniform int encoded;
        void main() { vec3 s = straight(texture(a, uv)); if (encoded == 1) s = encode(s);
                      float k = clamp((dot(s, REC709) - low) / max(high - low, 1e-9), 0.0, 1.0);
                      result = vec4(inv == 1 ? 1.0 - k : k, 0.0, 0.0, 1.0); }""",
    "over": """uniform sampler2D front; uniform sampler2D back; uniform sampler2D matte; uniform int has_matte;
        uniform float mixing;
        void main() { vec4 f = texture(front, uv); if (has_matte == 1) f *= texture(matte, uv).r; f *= mixing;
                      result = f + texture(back, uv) * (1.0 - f.a); }""",
    "mix": """uniform sampler2D a; uniform sampler2D b; uniform sampler2D by; uniform int by_matte; uniform float weight;
        void main() { float w = by_matte == 1 ? texture(by, uv).r : weight;
                      result = mix(texture(a, uv), texture(b, uv), w); }""",
    "blend": """uniform sampler2D a; uniform sampler2D b; uniform int mode; uniform float mixing;
        void main() { vec4 x = texture(a, uv), y = texture(b, uv), r;
          if (mode == 0) r = x + y - x * y; else if (mode == 1) r = x + y; else if (mode == 2) r = x * y;
          else if (mode == 3) r = max(x, y); else if (mode == 4) r = min(x, y); else if (mode == 5) r = abs(x - y);
          else r = mix(2.0 * x * y, 1.0 - 2.0 * (1.0 - x) * (1.0 - y), step(0.5, x));
          r = mix(x, r, mixing); r.a = max(x.a, y.a); result = r; }""",
    "porter_duff": """uniform sampler2D a; uniform sampler2D b; uniform int how;
        void main() { vec4 x = texture(a, uv), y = texture(b, uv);
          if (how == 0) result = x + y * (1.0 - x.a); else if (how == 1) result = y + x * (1.0 - y.a);
          else if (how == 2) result = x * y.a; else if (how == 3) result = x * (1.0 - y.a);
          else if (how == 4) result = x * y.a + y * (1.0 - x.a); else result = x * (1.0 - y.a) + y * (1.0 - x.a); }""",
    "pin": """uniform sampler2D a; uniform mat3 inverse_h; uniform vec2 picture_size;
        void main() { vec3 s = inverse_h * vec3(uv, 1.0);
          if (s.z <= 0.0) { result = vec4(0.0); return; }
          vec2 q = s.xy / s.z;
          // Transparent outside the picture, with the same one-pixel ramp the reference's bilinear sampling has.
          vec2 px = q * picture_size - 0.5; vec2 inside = clamp(min(px + 1.0, picture_size - px), 0.0, 1.0);
          result = texture(a, q) * inside.x * inside.y; }""",
    "grade": """uniform sampler2D a; uniform vec3 lift; uniform vec3 gain; uniform vec3 gam; uniform float saturation;
        void main() { vec4 p = texture(a, uv); vec3 c = straight(p);
          c = pow(max(c * gain + lift * (1.0 - c), 0.0), 1.0 / gam);
          float g = dot(c, REC709); c = g + (c - g) * saturation; result = vec4(c * p.a, p.a); }""",
    "invert": """uniform sampler2D a; uniform int is_matte;
        void main() { vec4 p = texture(a, uv);
          result = is_matte == 1 ? vec4(1.0 - p.r, 0.0, 0.0, 1.0) : vec4(p.a - p.rgb, p.a); }""",
    "blur": """uniform sampler2D a; uniform vec2 step_; uniform float sigma; uniform int half_;
        void main() { vec4 total = vec4(0.0); float weight = 0.0;
          for (int i = -half_; i <= half_; i++) { float w = exp(-0.5 * float(i * i) / (sigma * sigma));
            total += w * texture(a, uv + step_ * float(i)); weight += w; }
          result = total / weight; }""",
    "reduce": """uniform sampler2D a; uniform int factor; uniform vec2 big;
        void main() { vec4 total = vec4(0.0); vec2 base = floor(uv * big / float(factor)) * float(factor);
          for (int y = 0; y < factor; y++) for (int x = 0; x < factor; x++)
            total += texelFetch(a, ivec2(base) + ivec2(x, y), 0);
          result = total / float(factor * factor); }""",
}

_MESH_VERTEX = """#version 330
in vec2 screen; in float depth; in vec2 texel; in float light;
noperspective out vec2 tuv; noperspective out float shade;
void main() { tuv = texel; shade = light;
  // Screen fractions, top row first, to clip space; nearer surfaces win the depth test.
  gl_Position = vec4(screen.x * 2.0 - 1.0, screen.y * 2.0 - 1.0, clamp(depth / 1000.0, -1.0, 1.0), 1.0); }
"""
_MESH_FRAGMENT = """#version 330
uniform sampler2D a;
noperspective in vec2 tuv; noperspective in float shade;
out vec4 result;
void main() { vec4 p = texture(a, tuv); result = vec4(p.rgb * shade, p.a); }
"""


class GLRenderer:
    """One GL context, its programs compiled once, and textures reused from frame to frame."""

    def __init__(self) -> None:
        try:
            import moderngl
        except ImportError as error:
            raise ValidationError("The GL renderer needs ModernGL (the gpu extra)") from error
        self.gl = moderngl
        self.context = moderngl.create_standalone_context()
        quad = struct.pack("12f", -1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1)
        self.quad = self.context.buffer(quad)
        self.programs = {name: self.context.program(vertex_shader=_VERTEX, fragment_shader=_HEAD + body)
                         for name, body in _SHADERS.items()}
        self.vaos = {name: self.context.vertex_array(program, [(self.quad, "2f", "position")])
                     for name, program in self.programs.items()}
        self.mesh_program = self.context.program(vertex_shader=_MESH_VERTEX, fragment_shader=_MESH_FRAGMENT)
        self.opaque: dict[str, Any] = {}
        self.pool: dict[tuple, list] = {}

    @property
    def name(self) -> str:
        return self.context.info["GL_RENDERER"]

    def release(self) -> None:
        self.context.release()

    # --- textures -----------------------------------------------------------------

    def texture(self, size: tuple[int, int], components: int, data: bytes | None = None):
        texture = self.context.texture(size, components, data, dtype="f4")
        texture.repeat_x = texture.repeat_y = False
        return texture

    def upload(self, array: np.ndarray):
        array = np.ascontiguousarray(array, dtype=np.float32)
        components = 1 if array.ndim == 2 else array.shape[-1]
        return self.texture((array.shape[1], array.shape[0]), components, array.tobytes())

    def download(self, texture, components: int) -> np.ndarray:
        data = np.frombuffer(texture.read(), dtype=np.float32)
        return data.reshape(texture.height, texture.width, texture.components)[..., :components].copy()

    def draw(self, program: str, size: tuple[int, int], components: int, textures: dict[str, Any],
             **uniforms: Any):
        target = self.texture(size, components)
        frame = self.context.framebuffer([target])
        frame.use()
        self.context.viewport = (0, 0, size[0], size[1])
        shader = self.programs[program]
        for unit, (name, texture) in enumerate(textures.items()):
            texture.use(unit)
            if name in shader:
                shader[name].value = unit
        for name, value in uniforms.items():
            if name in shader:
                shader[name].value = value
        self.vaos[program].render()
        frame.release()
        return target

    # --- the graph ------------------------------------------------------------------

    def evaluate(self, graph: dict[str, Any], inputs: dict[str, Any], *, frames: int, size: tuple[int, int],
                 fps: float, working: str = LINEAR, root=None, beats: list[float] | None = None,
                 stream: bool = False) -> Any:
        """As `reference.evaluate`, drawn in GL. Refuses, by name, what it does not implement."""

        problems = validate(graph)
        if problems:
            raise ValidationError("The graph is not valid: " + "; ".join(message for _, message in problems))
        nodes = graph["nodes"]
        missing = sorted({node["op"] for node in nodes.values() if node["op"] not in IMPLEMENTED})
        if missing:
            raise ValidationError(f"The GL renderer does not implement {', '.join(missing)}")
        width, height = size
        aspect = width / height
        length = frames / fps
        curves: dict[str, Callable] = {name: value for name, value in inputs.items() if callable(value)}
        for name, kind in (graph.get("ports") or {}).items():
            if kind == "curve" and name not in curves:
                curves[name] = lambda seconds: seconds / length if length else 0.0
        curve = curve_factory(nodes, curves, fps=fps, length=length, beats=beats,
                              tracks=lambda reference: (_ for _ in ()).throw(
                                  ValidationError("The GL renderer does not read tracks")))
        clips: dict[str, Any] = {}
        for name, value in inputs.items():
            if callable(value):
                continue
            if isinstance(value, (Clip, _Held)) or (isinstance(value, np.ndarray) and value.ndim == 4):
                clips[name] = value
            elif isinstance(value, np.ndarray):
                clips[name] = _Held(value, frames)
            else:
                from pathlib import Path

                clips[name] = read(Path(value), frames, size, fps, working=working)

        def each():
            for frame in range(frames):
                # Standalone contexts share one "current" slot (another context may be current): claim ours.
                with self.context:
                    yield frame_of(frame)

        def frame_of(frame: int) -> np.ndarray:
            made: dict[str, Any] = {}
            seconds = (frame + 0.5) / fps

            def param(node: dict[str, Any], key: str, default: Any = None) -> Any:
                # An author's value, else the op's default as decided once in `semantics` (CT-0072).
                given = node.get(key)
                if given is None:
                    given = semantic_default(node.get("op", ""), key, default)
                if isinstance(given, dict) and "curve" in given:
                    return curve(given["curve"])(seconds)
                return given

            def value(reference: str):
                if reference in made:
                    return made[reference]
                if reference in clips:
                    made[reference] = self.upload(clips[reference][frame])
                    return made[reference]
                if reference in curves or nodes.get(reference, {}).get("op", "").startswith("curve."):
                    return float(np.asarray(curve(reference)(seconds)).reshape(-1)[0])
                base, _, output = reference.partition(".")
                if output:
                    value(base)
                    return made[reference]
                made[reference] = self._compute(reference, nodes[reference], value, param, size, aspect,
                                                root, frames, fps, working, clips, frame, made)
                return made[reference]

            result = value(graph["output"])
            picture = self.download(result, 4) if result.components == 4 else _grey(self.download(result, 1))
            for texture in made.values():
                if hasattr(texture, "release"):
                    texture.release()
            return picture

        return each() if stream else np.stack(list(each()))

    def _compute(self, name, node, value, param, size, aspect, root, frames, fps, working, clips, frame, made):
        op = node["op"]
        width, height = size
        p = lambda key, default=None: param(node, key, default)  # noqa: E731
        if op == "generate.source":
            if name not in clips:
                from pathlib import Path

                path = Path(node.get("file") or node.get("take"))
                path = (root / path) if root and not path.is_absolute() else path
                clips[name] = read(path, frames, size, fps, start=float(node.get("start", 0.0)),
                                   colorspace=node.get("colorspace", "sRGB Encoded Rec.709 (sRGB)"),
                                   alpha=node.get("alpha", "straight"), working=working)
            return self.upload(clips[name][frame])
        if op == "generate.solid":
            colour = np.asarray(p("colour"), np.float32)
            alpha = float(colour[3]) if colour.size > 3 else 1.0
            return self.draw("solid", size, 4, {}, colour=tuple(float(c) * alpha for c in colour[:3]) + (alpha,))
        if op == "generate.gradient":
            colours = np.asarray(p("colours", [[0, 0, 0, 1], [1, 1, 1, 1]]), np.float32)
            return self.draw("gradient", size, 4, {}, c0=tuple(colours[0]), c1=tuple(colours[-1]),
                             radial=int(p("kind", "linear") == "radial"), angle=float(np.radians(p("angle", 0.0))))
        if op in ("signal.luminance", "signal.luma"):
            weights = tuple(float(w) for w in (node.get("weights") or REC709))
            return self.draw("luminance", size, 1, {"a": value(node["picture"])}, weights=weights,
                             encoded=int(op == "signal.luma"))
        if op == "signal.channel":
            index = {"red": 0, "green": 1, "blue": 2, "alpha": 3}.get(node["channel"])
            if index is None:
                raise ValidationError(f"The GL renderer does not give {node['channel']} as a signal")
            return self.draw("channel", size, 1, {"a": value(node["picture"])}, index=index)
        if op == "matte.from_signal":
            return self.draw("from_signal", size, 1, {"a": value(node["signal"])}, low=float(p("low", 0.0)),
                             high=float(p("high", 1.0)), gam=float(p("gamma", 1.0)), inv=int(bool(node.get("invert"))))
        if op == "matte.threshold":
            return self.draw("threshold", size, 1, {"a": self._matte(value(node["matte"]), size)},
                             progress=float(value(node["progress"])),
                             spread=threshold_spread(p("softness")))
        if op == "matte.combine":
            how = ("union", "intersect", "subtract", "multiply").index(node["how"])
            return self.draw("combine", size, 1, {"a": self._matte(value(node["a"]), size),
                                                  "b": self._matte(value(node["b"]), size)}, how=how)
        if op == "matte.key":
            if node["by"] not in ("luminance", "luma"):
                raise ValidationError(f"The GL renderer does not key by {node['by']} yet")
            return self.draw("key", size, 1, {"a": value(node["picture"])}, low=float(p("low")), high=float(p("high")),
                             inv=int(bool(node.get("invert"))), encoded=int(node["by"] == "luma"))
        if op == "merge.over":
            textures = {"front": value(node["front"]), "back": value(node["back"])}
            if node.get("matte"):
                textures["matte"] = self._matte(value(node["matte"]), size)
            return self.draw("over", size, 4, textures, has_matte=int(bool(node.get("matte"))),
                             mixing=float(p("mix", 1.0)))
        if op == "merge.mix":
            by = value(node["by"])
            textures = {"a": value(node["a"]), "b": value(node["b"])}
            if not isinstance(by, float):
                textures["by"] = self._matte(by, size)
            return self.draw("mix", size, 4, textures, by_matte=int(not isinstance(by, float)),
                             weight=by if isinstance(by, float) else 0.0)
        if op == "merge.blend":
            modes = ("screen", "add", "multiply", "lighten", "darken", "difference", "overlay")
            return self.draw("blend", size, 4, {"a": value(node["a"]), "b": value(node["b"])},
                             mode=modes.index(node["mode"]), mixing=float(p("mix", 1.0)))
        if op == "merge.porter_duff":
            how = ("over", "under", "in", "out", "atop", "xor").index(node["how"])
            return self.draw("porter_duff", size, 4, {"a": value(node["a"]), "b": value(node["b"])}, how=how)
        if op in ("warp.transform", "warp.corner_pin"):
            from .warp import UNIT, homography, transform_corners

            if op == "warp.transform":
                corners = transform_corners(translate=p("translate"), scale=p("scale"),
                                            rotate=p("rotate"), pivot=p("pivot"),
                                            perspective=float(p("perspective") or 0.0), aspect=aspect)
            else:
                if node.get("track"):
                    raise ValidationError("The GL renderer does not read tracks")
                corners = [list(map(float, corner)) for corner in p("corners")]
            inverse = np.linalg.inv(homography(UNIT, corners))
            source = value(node["in"])
            return self.draw("pin", size, source.components, {"a": source},
                             inverse_h=tuple(inverse.T.reshape(-1).astype(np.float32)),
                             picture_size=(float(width), float(height)))
        if op == "warp.surface":
            return self._surface(node, value, p, size, aspect, made, name)
        if op == "opaque.gl":
            return self._opaque(node, value, size)
        if op == "colour.grade":
            vector = lambda key, default: tuple(np.broadcast_to(np.asarray(p(key, default), np.float32), (3,)))  # noqa: E731
            return self.draw("grade", size, 4, {"a": value(node["in"])}, lift=vector("lift", 0.0),
                             gain=vector("gain", 1.0), gam=vector("gamma", 1.0),
                             saturation=float(p("saturation", 1.0)))
        if op == "colour.invert":
            source = value(node["in"])
            return self.draw("invert", size, source.components, {"a": source}, is_matte=int(source.components == 1))
        if op == "filter.blur":
            source = value(node["in"])
            radius = float(p("radius", 0.0))
            if radius <= 0:
                return self._identity(source, size)
            sigma, half = blur_kernel(radius)
            across = self.draw("blur", size, source.components, {"a": source}, step_=(1.0 / width, 0.0), sigma=sigma,
                               half_=half)
            down = self.draw("blur", size, source.components, {"a": across}, step_=(0.0, 1.0 / height), sigma=sigma,
                             half_=half)
            across.release()
            return down
        raise ValidationError(f"The GL renderer does not implement {op}")

    def _identity(self, source, size):
        return self.draw("mix", size, source.components, {"a": source, "b": source}, by_matte=0, weight=0.0)

    def _opaque(self, node, value, size):
        """A gl-transitions shader (the node's `shader`, a .glsl path), its `uniforms` and `textures` (port names)."""

        from pathlib import Path

        source_path = str(node["shader"])
        if source_path not in self.opaque:
            source = Path(source_path).read_text(encoding="utf-8")
            program = self.context.program(vertex_shader=_VERTEX, fragment_shader=_OPAQUE_HEAD + source + _OPAQUE_FOOT)
            vao = self.context.vertex_array(program, [(self.quad, "2f", "position")])
            self.opaque[source_path] = (program, vao)
        program, vao = self.opaque[source_path]
        textures = {"fromTexture": value(node["from"]), "toTexture": value(node["to"])}
        for uniform, port in (node.get("textures") or {}).items():
            textures[uniform] = value(port)
        target = self.texture(size, 4)
        frame = self.context.framebuffer([target])
        frame.use()
        self.context.viewport = (0, 0, size[0], size[1])
        for unit, (name, texture) in enumerate(textures.items()):
            texture.use(unit)
            if name in program:
                program[name].value = unit
        for name, given in (node.get("uniforms") or {}).items():
            if name in program:
                program[name].value = tuple(given) if isinstance(given, list) else given
        if "progress" in program:
            program["progress"].value = float(value(node["progress"]))
        if "ratio" in program:
            program["ratio"].value = size[0] / size[1]
        vao.render()
        frame.release()
        return target

    def _matte(self, texture, size):
        """A picture used as a matte is its alpha (SPEC-0012 §1)."""

        if texture.components == 1:
            return texture
        return self.draw("channel", size, 1, {"a": texture}, index=3)

    def _surface(self, node, value, p, size, aspect, made, name):
        from .warp import surface_mesh

        width, height = size
        factor = max(1, int(p("supersample")))
        mesh = surface_mesh(shape=node["shape"], morph=float(p("morph")), rotate=p("rotate"),
                            translate=p("translate"), scale=float(p("scale")),
                            perspective=float(p("perspective") or 0.0), light=float(p("light")),
                            detail=int(p("detail")), aspect=aspect)
        rows, columns = mesh["u"].shape[0] - 1, mesh["u"].shape[1] - 1
        vertices = np.stack([mesh["x"], mesh["y"], mesh["z"], mesh["u"], mesh["v"], mesh["shade"]], axis=-1)
        index = []
        for row in range(rows):
            for column in range(columns):
                a, b = row * (columns + 1) + column, row * (columns + 1) + column + 1
                c, d = a + columns + 1, b + columns + 1
                index += [a, b, d, a, d, c]
        buffer = self.context.buffer(vertices.reshape(-1, 6).astype("f4").tobytes())
        indices = self.context.buffer(np.asarray(index, dtype="i4").tobytes())
        vao = self.context.vertex_array(self.mesh_program, [(buffer, "2f 1f 2f 1f", "screen", "depth", "texel",
                                                             "light")], indices)
        big = (width * factor, height * factor)
        colour = self.texture(big, 4)
        depth = self.context.depth_texture(big)
        frame = self.context.framebuffer([colour], depth)
        frame.use()
        frame.clear(0.0, 0.0, 0.0, 0.0, depth=1.0)
        self.context.viewport = (0, 0, big[0], big[1])
        self.context.enable(self.gl.DEPTH_TEST)
        source = value(node["in"])
        source.use(0)
        self.mesh_program["a"].value = 0
        vao.render()
        self.context.disable(self.gl.DEPTH_TEST)
        reduced = self.draw("reduce", size, 4, {"a": colour}, factor=factor, big=(float(big[0]), float(big[1])))
        for item in (vao, buffer, indices, frame, colour, depth):
            item.release()
        return reduced


def _grey(matte: np.ndarray) -> np.ndarray:
    return np.concatenate([matte, matte, matte, np.ones_like(matte)], axis=-1)


_SHARED: list[Any] = []


def gl_unavailable_reason() -> str | None:
    """Why GL cannot run here, or None when it can."""

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


def renderer_for(graph: dict[str, Any]) -> "GLRenderer | None":
    """The GL renderer, when GL can run here and draws every op of ``graph``; else None (the reference draws).

    One context is made once and kept for the process: compiling the programs is the slow part.
    """

    if any(node.get("op") not in IMPLEMENTED for node in (graph.get("nodes") or {}).values()):
        return None
    if not _SHARED:
        if gl_unavailable_reason():
            return None
        try:
            _SHARED.append(GLRenderer())
        except Exception:  # a context that cannot be made: the reference draws instead
            return None
    return _SHARED[0]
