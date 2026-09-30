// Where the assistant can take the screen (ADR 0018). Kept apart from the
// assistant so the canvas can follow a request without loading CopilotKit.

export interface Navigation {
  room: string;
  scene: string;
  shot: string;
  id: string;
}

/** Where a navigation request lands when it leaves the current page. */
export function addressOf(where: Navigation): string {
  const query = (pairs: Record<string, string>) => `/?${new URLSearchParams(pairs)}`;
  if (where.room === "canvas") return "/app/";
  if (where.room === "editor") return "/app/script.html";
  if (where.room === "overview") return "/";
  if (where.room === "scene" && where.scene) return query({ scene: where.scene });
  if (where.room === "compare" && where.scene && where.shot) {
    return query({ scene: where.scene, shot: where.shot.toUpperCase().startsWith("P") ? where.shot : `P${where.shot}` });
  }
  return query({ view: where.room });
}

