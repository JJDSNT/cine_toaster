vec4 transition(vec2 uv) {
  float firstHalf = 1.0 - step(0.5, progress);
  float local = firstHalf > 0.5 ? progress * 2.0 : (progress - 0.5) * 2.0;
  float width = firstHalf > 0.5 ? 1.0 - local : local;
  float left = 0.5 - width * 0.5;
  float right = 0.5 + width * 0.5;
  float inside = step(left, uv.x) * step(uv.x, right);
  vec2 sampleUv = vec2((uv.x - left) / max(width, 0.001), uv.y);
  vec4 image = firstHalf > 0.5 ? getFromColor(sampleUv) : getToColor(sampleUv);
  vec4 background = firstHalf > 0.5 ? getToColor(uv) : getFromColor(uv);
  float shade = 0.72 + 0.28 * width;
  return mix(background, vec4(image.rgb * shade, image.a), inside);
}
