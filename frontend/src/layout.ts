// Where each card sits. Positions are presentation, not production state
// (ADR 0015): they are computed from the graph every time, so the same film
// always draws the same way and nothing needs saving.
//
// Scenes are rows in production order. A scene's header card starts the row,
// its shots follow left to right in shot order, and a shot's takes hang below
// it.

import type { GraphNode } from "./types.ts";

export const SIZES = {
  header: { width: 190, height: 150 },
  shot: { width: 230, height: 214 },
  take: { width: 198, height: 46 },
  gap: 56,
  takeGap: 26,
  takeStep: 54,
  rowGap: 90,
};

export interface Position {
  x: number;
  y: number;
}

export function layout(nodes: GraphNode[], options: { takes: boolean } = { takes: true }): Map<string, Position> {
  const positions = new Map<string, Position>();
  const scenes = nodes
    .filter((node) => node.type === "scene")
    .sort((a, b) => (a.type === "scene" && b.type === "scene" ? a.data.order - b.data.order : 0));

  let y = 0;
  for (const scene of scenes) {
    positions.set(scene.id, { x: 0, y });
    const shots = nodes
      .filter((node) => node.type === "shot" && node.scene === scene.scene)
      .sort((a, b) => (a.type === "shot" && b.type === "shot" ? a.data.order - b.data.order : 0));
    let deepest = 0;
    shots.forEach((shot, index) => {
      const x = SIZES.header.width + SIZES.gap + index * (SIZES.shot.width + SIZES.gap);
      positions.set(shot.id, { x, y });
      if (!options.takes || shot.type !== "shot") return;
      const takes = nodes.filter(
        (node) => node.type === "take" && node.scene === scene.scene && node.data.shot === shot.data.shot,
      );
      takes.forEach((take, row) => {
        positions.set(take.id, {
          x: x + (SIZES.shot.width - SIZES.take.width) / 2,
          y: y + SIZES.shot.height + SIZES.takeGap + row * SIZES.takeStep,
        });
      });
      deepest = Math.max(deepest, takes.length);
    });
    const takesDepth = deepest ? SIZES.takeGap + (deepest - 1) * SIZES.takeStep + SIZES.take.height : 0;
    y += Math.max(SIZES.header.height, SIZES.shot.height + takesDepth) + SIZES.rowGap;
  }
  return positions;
}
