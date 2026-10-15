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
import threading
from typing import Any, Callable

import numpy as np

from ..errors import ValidationError
from .reference import (LINEAR, REC709, Clip, Shifted, TrackBook, _from_held, _Held, curve_factory, open_source,
                        pinned_corners, reach, read, source_extents, temporal_window)
from .schema import validate
from .semantics import blur_kernel, pixels, screen_channel, threshold_spread
from .semantics import default as semantic_default

IMPLEMENTED = {
    "generate.source", "generate.solid", "generate.gradient", "generate.noise", "generate.text",
    "signal.luminance", "signal.luma", "signal.channel",
    "matte.from_signal", "matte.threshold", "matte.combine", "matte.key",
    "merge.over", "merge.mix", "merge.blend", "merge.porter_duff", "merge.channels",
    "warp.transform", "warp.corner_pin", "warp.surface", "warp.displace",
    "matte.shape",
    "colour.grade", "colour.invert", "colour.despill", "colour.lut", "colour.cycle",
    "filter.blur", "filter.morphology", "filter.noise", "filter.bevel",
    "curve.progress", "curve.keys", "curve.map", "curve.combine", "curve.noise", "curve.beats",
    "opaque.gl",
    # Time and tracks (C7 step 6, CT-0080): which frames, with what weights, and where a track is read are the
    # shared contract's (`clock`, `semantics.remap_samples`, `reference.TrackBook`); GL draws what it decides.
    "time.remap", "time.offset", "time.blend", "time.echo", "track.read", "track.measure", "curve.from_track",
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
float decode1(float c) { return c <= 0.04045 ? c / 12.92 : pow((c + 0.055) / 1.055, 2.4); }
vec3 decode(vec3 c) { return vec3(decode1(c.r), decode1(c.g), decode1(c.b)); }
"""

_SHADERS = {
    "solid": "uniform vec4 colour; void main() { result = colour; }",
    "gradient": """uniform vec4 stops[8]; uniform float places[8]; uniform int count; uniform int radial; uniform float angle;
        uniform float aspect; uniform float repeats;
        void main() {
          vec2 p = uv; vec2 d = p - 0.5; float x;
          if (radial == 1) x = length(d) / length(vec2(0.5));
          else if (radial == 2) x = length(vec2(d.x * aspect, d.y)) / length(vec2(0.5 * aspect, 0.5));
          else if (radial == 3) x = abs(d.x) + abs(d.y);
          else if (radial == 4) x = mod(atan(d.x * aspect, -d.y) / 6.283185307 - angle / 6.283185307, 1.0);
          else x = (p.x - 0.5) * cos(angle) + (p.y - 0.5) * sin(angle) + 0.5;
          if (repeats > 1.0) x = mod(clamp(x, 0.0, 1.0) * repeats, 1.0);
          x = clamp(x, 0.0, 1.0); int high = 1;
          for (int i = 1; i < 8; i++) { if (i < count && x >= places[i]) high = min(i + 1, count - 1); }
          int low = high - 1;
          float w = clamp((x - places[low]) / max(places[high] - places[low], 1e-6), 0.0, 1.0);
          vec4 c = count == 1 ? stops[0] : mix(stops[low], stops[high], w);
          result = vec4(c.rgb * c.a, c.a);
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
    "key": """uniform sampler2D a; uniform sampler2D plate; uniform float low; uniform float high; uniform int inv;
        uniform int encoded; uniform int method; uniform vec3 colour; uniform float tolerance; uniform float spread;
        uniform int screen;
        float excess(vec3 c) { return screen == 0 ? c.r - max(c.g, c.b) : (screen == 1 ? c.g - max(c.r, c.b)
                                                                             : c.b - max(c.r, c.g)); }
        void main() { vec3 s = straight(texture(a, uv)); float k;
          if (method == 0) { if (encoded == 1) s = encode(s);
                             k = clamp((dot(s, REC709) - low) / max(high - low, 1e-9), 0.0, 1.0); }
          else { vec3 e = encode(s); float d;
                 if (method == 1) d = 1.0 - excess(s) / max(excess(colour), 1e-6);
                 else { vec3 q = abs(e - encode(straight(texture(plate, uv)))); d = max(q.r, max(q.g, q.b)); }
                 k = clamp((d - tolerance) / spread, 0.0, 1.0); }
          result = vec4(inv == 1 ? 1.0 - k : k, 0.0, 0.0, 1.0); }""",
    "over": """uniform sampler2D front; uniform sampler2D back; uniform sampler2D matte; uniform int has_matte;
        uniform float mixing;
        void main() { vec4 f = texture(front, uv); if (has_matte == 1) f *= texture(matte, uv).r; f *= mixing;
                      result = f + texture(back, uv) * (1.0 - f.a); }""",
    "mix": """uniform sampler2D a; uniform sampler2D b; uniform sampler2D by; uniform int by_matte; uniform float weight;
        void main() { float w = by_matte == 1 ? texture(by, uv).r : weight;
                      result = mix(texture(a, uv), texture(b, uv), w); }""",
    "blend": """uniform sampler2D a; uniform sampler2D b; uniform int mode; uniform float mixing;
        void main() { vec4 x = texture(a, uv), y = texture(b, uv);
          vec3 cb = straight(x), cs = straight(y), f;
          if (mode == 0) f = cb + cs - cb * cs; else if (mode == 1) f = cb + cs; else if (mode == 2) f = cb * cs;
          else if (mode == 3) f = max(cb, cs); else if (mode == 4) f = min(cb, cs); else if (mode == 5) f = abs(cb - cs);
          else f = mix(2.0 * cb * cs, 1.0 - 2.0 * (1.0 - cb) * (1.0 - cs), step(0.5, cb));
          vec4 r = vec4(y.rgb * (1.0 - x.a) + x.rgb * (1.0 - y.a) + x.a * y.a * f, x.a + y.a - x.a * y.a);
          result = mix(x, r, mixing); }""",
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
    "despill": """uniform sampler2D a; uniform sampler2D m; uniform int has_matte; uniform vec3 screen_rgb;
        uniform int screen; uniform int average; uniform float amount;
        void main() { vec4 p = texture(a, uv);
          if (has_matte == 1) { float k = texture(m, uv).r;
            p = vec4(max(p.rgb - (1.0 - k) * screen_rgb * p.a, vec3(0.0)), p.a * k); }
          vec3 c = straight(p);
          float s = screen == 0 ? c.r : (screen == 1 ? c.g : c.b);
          float o1 = screen == 0 ? c.g : c.r, o2 = screen == 2 ? c.g : c.b;
          float cap = average == 1 ? 0.5 * (o1 + o2) : max(o1, o2);
          float held = mix(s, min(s, cap), amount);
          if (screen == 0) c.r = held; else if (screen == 1) c.g = held; else c.b = held;
          result = vec4(c * p.a, p.a); }""",
    "invert": """uniform sampler2D a; uniform int is_matte;
        void main() { vec4 p = texture(a, uv);
          result = is_matte == 1 ? vec4(1.0 - p.r, 0.0, 0.0, 1.0) : vec4(p.a - p.rgb, p.a); }""",
    "displace": """uniform sampler2D a; uniform sampler2D field; uniform int vectors; uniform vec2 direction;
        uniform float strength; uniform int edge; uniform vec2 picture;
        void main() { vec4 f = texture(field, uv); vec2 shift;
          if (vectors == 1) shift = f.rg * strength / picture;  // pixels, as the reference reads two channels
          else shift = (f.r - 0.5) * direction * strength;
          vec2 s = uv - shift;
          if (edge == 1) s = clamp(s, 0.5 / picture, 1.0 - 0.5 / picture);
          else if (edge == 2) { vec2 c = (s * picture - 0.5) / (picture - 1.0);
                                c = 1.0 - abs(mod(c, 2.0) - 1.0); s = (c * (picture - 1.0) + 0.5) / picture; }
          vec4 v = texture(a, s);
          if (edge == 0) { vec2 inside = step(-0.5 / picture, s) * step(s, 1.0 + 0.5 / picture); v *= inside.x * inside.y; }
          result = v; }""",
    "channels": """uniform sampler2D r; uniform sampler2D g; uniform sampler2D b; uniform sampler2D al;
        uniform ivec4 given;
        void main() { result = vec4(given.x == 1 ? texture(r, uv).r : 0.0, given.y == 1 ? texture(g, uv).r : 0.0,
                                    given.z == 1 ? texture(b, uv).r : 0.0, given.w == 1 ? texture(al, uv).r : 1.0); }""",
    "grain": """uniform sampler2D a; uniform sampler2D field; uniform float amount; uniform int shown_;
        void main() { vec4 p = texture(a, uv); float g = texture(field, uv).r * amount * 0.1;
          if (shown_ == 1) { vec3 s = encode(straight(p)); result = vec4(decode(max(s + g, vec3(0.0))) * p.a, p.a); }
          else result = vec4(max(p.rgb + g * p.a, vec3(0.0)), p.a); }""",
    "lut": """uniform sampler2D a; uniform sampler3D table; uniform float top; uniform float cells;
        void main() { vec4 p = texture(a, uv); vec3 c = max(straight(p), vec3(0.0));
          vec3 u = clamp(encode(c / (1.0 + c)) / top, 0.0, 1.0);
          vec3 o = texture(table, (u * (cells - 1.0) + 0.5) / cells).rgb; result = vec4(o * p.a, p.a); }""",
    "bevel": """uniform sampler2D a; uniform sampler2D relief; uniform vec2 texel; uniform float reach;
        uniform float depth; uniform vec3 light; uniform float highlight; uniform float shadow_;
        void main() { vec4 p = texture(a, uv);
          float sx = (texture(relief, uv + vec2(texel.x, 0.0)).r - texture(relief, uv - vec2(texel.x, 0.0)).r)
                     * 0.5 * max(reach, 1.0) * depth;
          float sy = (texture(relief, uv + vec2(0.0, texel.y)).r - texture(relief, uv - vec2(0.0, texel.y)).r)
                     * 0.5 * max(reach, 1.0) * depth;
          float shade = ((-sx * light.x - sy * light.y + light.z) / sqrt(sx * sx + sy * sy + 1.0)) / max(light.z, 1e-6);
          float lit = max(shade - 1.0, 0.0), dark = max(1.0 - shade, 0.0);
          result = vec4(max(p.rgb * (1.0 - shadow_ * dark) + highlight * lit * p.a, vec3(0.0)), p.a); }""",
    "cycle": """uniform sampler2D a; uniform mat3 turn;
        void main() { vec4 p = texture(a, uv); result = vec4(max(turn * straight(p), vec3(0.0)) * p.a, p.a); }""",
    "morphology": """uniform sampler2D a; uniform vec2 texel; uniform int reach; uniform int grow;
        void main() { float m = grow == 1 ? 0.0 : 1.0;
          for (int y = -reach; y <= reach; y++) for (int x = -reach; x <= reach; x++) {
            float v = texture(a, uv + texel * vec2(float(x), float(y))).r; m = grow == 1 ? max(m, v) : min(m, v); }
          result = vec4(m, 0.0, 0.0, 1.0); }""",
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
        self.shapes: dict[str, np.ndarray] = {}  # shapes drawn by the shared rasteriser, by what they are
        self.luts: dict[str, Any] = {}  # looks baked from the reference's own colour function, by what they are

    @property
    def name(self) -> str:
        return self.context.info["GL_RENDERER"]

    def release(self) -> None:
        self.context.release()

    # --- textures -----------------------------------------------------------------

    #: Textures let go are kept for the next draw of their size, up to this many of each (CT-0080, step 6):
    #: allocating one cost 7 ms at 1280x720, more than most draws.
    POOLED = 48

    def texture(self, size: tuple[int, int], components: int, data: bytes | None = None):
        pool = self.__dict__.setdefault("_pool", {}).get((tuple(size), components))
        if pool:
            texture = pool.pop()
            if data is not None:
                texture.write(data)
            return texture
        texture = self.context.texture(size, components, data, dtype="f4")
        texture.repeat_x = texture.repeat_y = False
        return texture

    def recycle(self, texture) -> None:
        """A texture no longer needed, kept for the next of its size (its framebuffer with it)."""

        pool = self.__dict__.setdefault("_pool", {}).setdefault((tuple(texture.size), texture.components), [])
        if len(pool) < self.POOLED:
            pool.append(texture)
            return
        if getattr(texture, "extra", None) is not None:
            texture.extra.release()
        texture.release()

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
        frame = getattr(target, "extra", None)
        if frame is None:  # a framebuffer kept with its texture (moderngl's `extra`): made once, not every draw
            frame = target.extra = self.context.framebuffer([target])
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
        return target

    # --- the graph ------------------------------------------------------------------

    def evaluate(self, graph: dict[str, Any], inputs: dict[str, Any], *, frames: int, size: tuple[int, int],
                 fps: float, working: str = LINEAR, root=None, beats: list[float] | None = None,
                 stream: bool = False, origins: dict[str, Any] | None = None) -> Any:
        """As `reference.evaluate`, drawn in GL. Refuses, by name, what it does not implement.

        A node may be asked for at another frame than the one being made (a time operation): values are kept by
        (node, frame), as long as the graph's time operations may still reach back to them."""

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
        # How far its sources are read, ahead and back: the reference's own reckoning (`clock`), not GL's.
        extent = reach(graph, frames, fps, beats)
        spans = source_extents(graph, frames, fps, beats)
        window = temporal_window(graph) + 1
        curves: dict[str, Callable] = {name: value for name, value in inputs.items() if callable(value)}
        for name, kind in (graph.get("ports") or {}).items():
            if kind == "curve" and name not in curves:
                curves[name] = lambda seconds: seconds / length if length else 0.0
        clips: dict[str, Any] = {}
        for name, value in inputs.items():
            if callable(value) or isinstance(value, dict):
                continue
            if isinstance(value, (Clip, _Held, Shifted)) or (isinstance(value, np.ndarray) and value.ndim == 4):
                clips[name] = value
            elif isinstance(value, np.ndarray):
                clips[name] = _Held(value, extent)
            else:
                from pathlib import Path

                clips[name] = read(Path(value), extent, size, fps, working=working)
        kept: dict[tuple[str, int], Any] = {}  # (node, frame) -> its texture
        temporary: list[Any] = []  # textures made on the way (a blend's steps), let go after each frame
        book = TrackBook(graph, inputs, fps=fps, frames=frames, root=root, origins=origins or {}, working=working,
                         picture_at=lambda name, index: self._picture(value_at(name, index)))
        curve = curve_factory(nodes, curves, fps=fps, length=length, beats=beats, tracks=book.track,
                              track_entry=lambda reference, seconds: book.entry(reference, book.reader[0], seconds))
        book.curve = curve

        def param_at(frame: int) -> Callable:
            seconds = (frame + 0.5) / fps

            def param(node: dict[str, Any], key: str, default: Any = None) -> Any:
                # An author's value, else the op's default as decided once in `semantics` (CT-0072).
                given = node.get(key)
                if given is None:
                    given = semantic_default(node.get("op", ""), key, default)
                if isinstance(given, dict) and "curve" in given:
                    return curve(given["curve"])(seconds)
                return given

            return param

        def value_at(reference: str, frame: int) -> Any:
            key = (reference, frame)
            if key in kept:
                return kept[key]
            if reference in clips:
                kept[key] = self.upload(_from_held(clips[reference], frame))
                return kept[key]
            if reference in curves or nodes.get(reference, {}).get("op", "").startswith("curve."):
                return float(np.asarray(curve(reference)((frame + 0.5) / fps)).reshape(-1)[0])
            base, _, output = reference.partition(".")
            if output:
                value_at(base, frame)
                return kept[key]
            book.reader[0] = reference
            kept[key] = self._compute(reference, nodes[reference], lambda name: value_at(name, frame),
                                      param_at(frame), size, aspect, root, frames, fps, working, clips, frame,
                                      _Made(kept, frame), value_at=value_at, book=book, spans=spans, extent=extent,
                                      temporary=temporary)
            return kept[key]

        def let_go(keep_from: int, keep_to: int) -> None:
            held = {id(texture) for (name, frame), texture in kept.items() if keep_from <= frame <= keep_to}
            for key in [key for key in kept if not keep_from <= key[1] <= keep_to]:
                texture = kept.pop(key)
                if hasattr(texture, "release") and id(texture) not in held:
                    held.add(id(texture))  # the same texture under two keys (a remap's): let go once
                    self.recycle(texture)
            for texture in temporary:
                if hasattr(texture, "release") and id(texture) not in held:
                    held.add(id(texture))
                    self.recycle(texture)
            temporary.clear()

        def each():
            for frame in range(frames):
                # Standalone contexts share one "current" slot (another context may be current): claim ours.
                with self.context:
                    result = value_at(graph["output"], frame)
                    picture = self.download(result, 4) if result.components == 4 else _grey(self.download(result, 1))
                    let_go(frame + 1 - window, frame)
                    yield picture
            with self.context:
                let_go(1, 0)

        return each() if stream else np.stack(list(each()))

    def _picture(self, texture: Any) -> np.ndarray:
        """A texture as a picture on the CPU (for OpenCV's tracking): the one transfer back a track asks for."""

        return self.download(texture, 4) if texture.components == 4 else _grey(self.download(texture, 1))

    def _compute(self, name, node, value, param, size, aspect, root, frames, fps, working, clips, frame, made, *,
                 value_at=None, book=None, spans=None, extent=None, temporary=None):
        op = node["op"]
        width, height = size
        p = lambda key, default=None: param(node, key, default)  # noqa: E731
        if op == "generate.source":
            if name not in clips:
                from pathlib import Path

                path = Path(node.get("file") or node.get("take"))
                path = (root / path) if root and not path.is_absolute() else path
                clips[name] = open_source(path, node, name, spans or {}, extent or frames, size, fps, working)
            return self.upload(_from_held(clips[name], frame))
        if op in ("time.remap", "time.offset", "time.blend", "time.echo"):
            return self._time(name, node, p, value_at, size, frames, fps, frame, temporary, book)
        if op == "generate.solid":
            colour = np.asarray(p("colour"), np.float32)
            alpha = float(colour[3]) if colour.size > 3 else 1.0
            return self.draw("solid", size, 4, {}, colour=tuple(float(c) * alpha for c in colour[:3]) + (alpha,))
        if op == "generate.gradient":
            colours = np.asarray(p("colours", [[0, 0, 0, 1], [1, 1, 1, 1]]), np.float32)
            kinds = ("linear", "radial", "circle", "diamond", "conic")
            from .reference import gradient_stops

            colour_stops, places = gradient_stops(colours, p("at", None))
            stops = [tuple(float(c) for c in colour) for colour in colour_stops]
            return self.draw("gradient", size, 4, {}, stops=tuple(stops + [stops[-1]] * (8 - len(stops))),
                             places=tuple(float(v) for v in places) + (1.0,) * (8 - len(places)), count=len(stops),
                             radial=kinds.index(p("kind", "linear")), angle=float(np.radians(p("angle", 0.0))),
                             aspect=width / height, repeats=float(p("repeat", 1.0) or 1.0))
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
            by = node["by"]
            textures = {"a": value(node["picture"])}
            if by == "difference":
                textures["plate"] = value(node["reference"])
            if by in ("luminance", "luma"):
                return self.draw("key", size, 1, textures, low=float(p("low")), high=float(p("high")),
                                 inv=int(bool(node.get("invert"))), encoded=int(by == "luma"), method=0)
            colour = tuple(float(c) for c in (list(p("colour") or [0, 0, 0]) + [0, 0, 0])[:3])
            return self.draw("key", size, 1, textures, inv=int(bool(node.get("invert"))),
                             method=1 if by == "colour" else 2, colour=colour, tolerance=float(p("tolerance")),
                             screen=screen_channel(colour),
                             spread=threshold_spread(p("softness", 0.0)))
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
                                            perspective=float(p("perspective") or 0.0), aspect=aspect,
                                            skew=float(p("skew", 0.0) or 0.0))
            elif node.get("track"):
                # Where the track says, read the one way (`reference.pinned_corners`): validated, corrected, by
                # its clock -- GL draws the pin it is given.
                corners = pinned_corners(book, node, name, (frame + 0.5) / fps, fps)
            else:
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
        if op == "colour.despill":
            textures = {"a": value(node["in"])}
            if node.get("matte"):
                textures["m"] = self._matte(value(node["matte"]), size)
            screen_rgb = tuple(float(c) for c in (list(p("colour")) + [0, 0, 0])[:3])
            return self.draw("despill", size, 4, textures, screen=screen_channel(screen_rgb), screen_rgb=screen_rgb,
                             has_matte=int(bool(node.get("matte"))), average=int(p("limit", "max") == "average"),
                             amount=float(p("amount", 1.0)))
        if op == "colour.invert":
            source = value(node["in"])
            return self.draw("invert", size, source.components, {"a": source}, is_matte=int(source.components == 1))
        if op == "filter.blur":
            source = value(node["in"])
            radius = pixels(p("radius", 0.0), height)
            if radius <= 0:
                return self._identity(source, size)
            sigma, half = blur_kernel(radius)
            across = self.draw("blur", size, source.components, {"a": source}, step_=(1.0 / width, 0.0), sigma=sigma,
                               half_=half)
            down = self.draw("blur", size, source.components, {"a": across}, step_=(0.0, 1.0 / height), sigma=sigma,
                             half_=half)
            self.recycle(across)
            return down
        if op == "matte.shape":
            # Drawn by the rasteriser the reference uses (one drawing of a shape), once per shape and size, and
            # uploaded: a garbage matte or a window does not change from frame to frame unless its size does.
            from .reference import _shape

            scale = float(p("size", 1.0))
            key = repr((node.get("shape"), node.get("points"), node.get("feather"), scale, size))
            if key not in self.shapes:
                if len(self.shapes) > 32:
                    self.shapes.clear()
                self.shapes[key] = _shape(node, size, scale)
            return self.upload(self.shapes[key])
        if op == "colour.lut":
            table, top, cells = self._lut(node, working, root)
            return self.draw("lut", size, 4, {"a": value(node["in"]), "table": table}, top=top, cells=float(cells))
        if op == "filter.bevel":
            from .semantics import light_direction

            source = value(node["in"])
            reach = pixels(p("radius", 6.0), height)
            alpha = self.draw("channel", size, 1, {"a": source}, index=3)
            if reach > 0:
                sigma, half = blur_kernel(reach)
                across = self.draw("blur", size, 1, {"a": alpha}, step_=(1.0 / width, 0.0), sigma=sigma, half_=half)
                relief = self.draw("blur", size, 1, {"a": across}, step_=(0.0, 1.0 / height), sigma=sigma, half_=half)
            else:
                relief = alpha
            return self.draw("bevel", size, 4, {"a": source, "relief": relief}, texel=(1.0 / width, 1.0 / height),
                             reach=reach, depth=float(p("depth", 1.0)),
                             light=light_direction(p("angle", 135.0), p("elevation", 35.0)),
                             highlight=float(p("highlight", 0.6)), shadow_=float(p("shadow", 0.6)))
        if op == "colour.cycle":
            from .semantics import hue_turn

            matrix = hue_turn(float(p("speed", 90.0)) * (frame + 0.5) / fps)
            column_major = tuple(matrix[row][col] for col in range(3) for row in range(3))
            return self.draw("cycle", size, 4, {"a": value(node["in"])}, turn=column_major)
        if op == "merge.channels":
            textures, given = {}, []
            for channel, uniform in (("red", "r"), ("green", "g"), ("blue", "b"), ("alpha", "al")):
                if node.get(channel):
                    textures[uniform] = value(node[channel])
                given.append(int(bool(node.get(channel))))
            return self.draw("channels", size, 4, textures, given=tuple(given))
        if op == "generate.text":
            # The reference's own drawing of the text (kept while it does not change), uploaded: one text, the same
            # in both renderers (CT-0077).
            from .reference import text_picture

            return self.upload(text_picture(node, p, width, height, root, (frame + 0.5) / fps))
        if op == "generate.noise":
            # The reference's own field, uploaded: noise drawn once, the same in both renderers (CT-0077).
            from .reference import noise_field

            grey = noise_field(str(p("kind", "value")), float(p("scale", 8.0)), int(p("seed", 0) or 0), frame,
                               width, height)
            return self.upload(np.stack([grey, grey, grey, np.ones_like(grey)], axis=-1))
        if op == "filter.noise":
            from .reference import grain_field

            field = self.upload(grain_field(int(p("seed", 0) or 0), frame, float(p("size", 1.0)), width, height))
            return self.draw("grain", size, 4, {"a": value(node["in"]), "field": field},
                             amount=float(p("amount", 0.1)), shown_=int(p("space", "linear") == "display"))
        if op == "warp.displace":
            source, field = value(node["in"]), value(node["map"])
            direction = tuple(float(c) for c in np.broadcast_to(np.asarray(p("direction") if p("direction") is not None
                                                                         else [1.0, 0.0], np.float32), (2,)))
            return self.draw("displace", size, source.components, {"a": source, "field": field},
                             vectors=int(field.components >= 2), direction=direction,
                             strength=float(p("strength", 0.1)), picture=(float(width), float(height)),
                             edge=("transparent", "extend", "mirror").index(str(node.get("edge", "transparent"))))
        if op == "filter.morphology":
            source = value(node["in"])
            reach = max(0, int(round(pixels(p("radius", 1.0), height))))
            if reach == 0:
                return self._identity(source, size)
            return self.draw("morphology", size, 1, {"a": source}, texel=(1.0 / width, 1.0 / height), reach=reach,
                             grow=int(node["operation"] == "dilate"))
        raise ValidationError(f"The GL renderer does not implement {op}")

    def _lut(self, node, working, root, cells: int = 33, top: float = 0.995):
        """A look as a 3D table, baked once by the reference's own `lut_colours` (one drawing of a look) over a
        lattice even in the encoded value of x / (1 + x): fine in the shadows, reaching about 80 times white."""

        from .reference import decode_srgb, lut_colours

        key = repr((node.get("file"), node.get("look"), node.get("view"), node.get("display"), working, str(root)))
        if key not in self.luts:
            steps = decode_srgb(np.linspace(0.0, top, cells, dtype=np.float32))
            light = steps / (1.0 - steps)
            b, g, r = np.meshgrid(light, light, light, indexing="ij")  # red fastest, as a 3D texture is laid out
            lattice = np.stack([r, g, b], axis=-1).reshape(1, -1, 3).astype(np.float32)
            baked = lut_colours(node, lattice, working, root).reshape(cells, cells, cells, 3).astype(np.float32)
            table = self.context.texture3d((cells, cells, cells), 3, np.ascontiguousarray(baked).tobytes(), dtype="f4")
            table.filter = (self.gl.LINEAR, self.gl.LINEAR)
            table.repeat_x = table.repeat_y = table.repeat_z = False
            self.luts[key] = table
        return self.luts[key], top, cells

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

    def _time(self, name, node, p, value_at, size, frames, fps, frame, temporary, book):
        """A time operation: which frames of its input, with what weights, decided by the shared contract
        (`clock.remap_at`, `semantics.remap_samples`, the reference's clamps); GL only mixes them."""

        from . import clock
        from .semantics import remap_samples

        op = node["op"]
        if op == "time.offset":
            return value_at(node["in"], frame - int(p("frames", 0)))
        if op == "time.remap":
            samples = remap_samples(clock.remap_at(node, book.nodes, book.curve, clock.centre(frame, fps)), fps,
                                    str(node.get("interpolation") or "nearest"), clamp=False)
            if len(samples) == 1:
                return value_at(node["in"], samples[0][0])
            (first, _), (second, weight) = samples
            a, b = value_at(node["in"], first), value_at(node["in"], second)
            return self.draw("mix", size, a.components, {"a": a, "b": b}, by_matte=0, weight=float(weight))
        if op == "time.blend":
            span = max(1, int(p("frames", 2)))
            around = [int(np.clip(frame + offset, 0, frames - 1)) for offset in range(-(span // 2), span - span // 2)]
            total = value_at(node["in"], around[0])
            for count, index in enumerate(around[1:], 2):
                made = self.draw("mix", size, total.components, {"a": total, "b": value_at(node["in"], index)},
                                 by_matte=0, weight=1.0 / count)  # a running mean: the average of all
                temporary.append(made)
                total = made
            return total
        count, spacing = int(p("count", 4)), max(1, int(p("spacing", 1)))
        decay = float(p("decay", 0.5))
        out = self.draw("solid", size, 4, {}, colour=(0.0, 0.0, 0.0, 0.0))
        for index in range(count, -1, -1):  # the oldest echo first, the present last, on top
            earlier = frame - index * spacing
            if earlier < 0:
                continue
            temporary.append(out)
            out = self.draw("over", size, 4, {"front": value_at(node["in"], earlier), "back": out}, has_matte=0,
                            mixing=float(decay ** index))
        return out

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


class _Made:
    """The values made at one frame, as a node with several outputs writes them (`made["node.depth"]`): a view of
    the renderer's values kept by (node, frame)."""

    def __init__(self, kept: dict[tuple[str, int], Any], frame: int) -> None:
        self.kept, self.frame = kept, frame

    def __getitem__(self, reference: str) -> Any:
        return self.kept[(reference, self.frame)]

    def __setitem__(self, reference: str, value: Any) -> None:
        self.kept[(reference, self.frame)] = value

    def __contains__(self, reference: str) -> bool:
        return (reference, self.frame) in self.kept


#: One renderer per thread: a GL context is current in the thread that made it, and making it current in another
#: (a preview rendered in a worker) is refused by GLX -- Xlib then ends the process (CT-0077).
_SHARED = threading.local()


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

    One context is made once per thread and kept: compiling the programs is the slow part.
    """

    # An OpenFX plugin is Natron's, staged before any renderer draws (`natron.stage`): not GL's to refuse.
    if any(node.get("op") not in IMPLEMENTED and node.get("op") != "opaque.natron"
           for node in (graph.get("nodes") or {}).values()):
        return None
    renderer = getattr(_SHARED, "renderer", None)
    if renderer is None:
        if gl_unavailable_reason():
            return None
        try:
            renderer = _SHARED.renderer = GLRenderer()
        except Exception:  # a context that cannot be made: the reference draws instead
            return None
    return renderer
