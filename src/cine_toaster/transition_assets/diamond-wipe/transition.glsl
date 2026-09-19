vec4 transition(vec2 uv) {
  vec2 centered = abs(uv - vec2(0.5));
  float distanceFromCenter = centered.x + centered.y;
  float edge = progress * 1.15;
  float mask = 1.0 - smoothstep(edge - 0.035, edge + 0.035, distanceFromCenter);
  return mix(getFromColor(uv), getToColor(uv), mask);
}
