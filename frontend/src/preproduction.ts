// A navigation projection only: URLs retain scene/shot/study selection, never film state.
export interface Focus { scene: string; shot: string; study: boolean }
export interface ShotKey { shot_id: string }
export interface SceneKey { id: string; frames: ShotKey[] }

export function resolveFocus(scenes: SceneKey[], search: string): Focus {
  const query = new URLSearchParams(search);
  const scene = scenes.find((item) => item.id === query.get("scene")) ?? scenes[0];
  const shot = scene?.frames.find((item) => item.shot_id === query.get("shot")) ?? scene?.frames[0];
  return { scene: scene?.id ?? "", shot: shot?.shot_id ?? "", study: query.get("study") === "1" };
}

export function focusSearch(focus: Focus): string {
  const query = new URLSearchParams();
  if (focus.scene) query.set("scene", focus.scene);
  if (focus.shot) query.set("shot", focus.shot);
  if (focus.study) query.set("study", "1");
  return query.size ? `?${query}` : "";
}

export function mediaAddress(path: string): string {
  return `/media/${path.split("/").map(encodeURIComponent).join("/")}`;
}
