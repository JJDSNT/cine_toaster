vec4 transition(vec2 uv) {
  if (progress <= 0.0) {
    return getFromColor(uv);
  }
  if (progress >= 1.0) {
    return getToColor(uv);
  }

  float edge = progress * 1.2 - 0.1;
  float reveal = 1.0 - smoothstep(edge - 0.035, edge + 0.035, uv.x);
  vec4 incoming = getToColor(uv);

  float bars = 0.5 + 0.5 * sin((uv.y * 9.0 + progress * 2.0) * 6.2831853);
  float nearEdge = 1.0 - smoothstep(0.0, 0.16, abs(uv.x - edge));
  vec3 copper = vec3(0.83, 0.37, 0.12);
  incoming.rgb = mix(incoming.rgb, copper, bars * nearEdge * 0.55);

  return mix(getFromColor(uv), incoming, reveal);
}
