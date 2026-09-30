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
  run: { width: 190, height: 190 },
  gap: 56,
  takeGap: 26,
  takeStep: 54,
  rowGap: 90,
};

export interface Position {
  x: number;
  y: number;
}

export interface LayoutOptions {
  takes: boolean;
  /** Shots per line before a long scene wraps onto the next one. */
  perRow: number;
}

export const DEFAULT_OPTIONS: LayoutOptions = { takes: true, perRow: 8 };

export function layout(nodes: GraphNode[], options: Partial<LayoutOptions> = {}): Map<string, Position> {
  const { takes: showTakes, perRow } = { ...DEFAULT_OPTIONS, ...options };
  const positions = new Map<string, Position>();
  const scenes = nodes
    .filter((node) => node.type === "scene")
    .sort((a, b) => (a.type === "scene" && b.type === "scene" ? a.data.order - b.data.order : 0));

  let y = 0;
  for (const scene of scenes) {
    positions.set(scene.id, { x: 0, y });
    // Workflow runs stack under the scene's header card, beside the shots they make.
    const runs = nodes.filter((node) => node.type === "run" && node.scene === scene.scene);
    runs.forEach((run, index) => {
      positions.set(run.id, { x: 0, y: y + SIZES.header.height + SIZES.takeGap + index * (SIZES.run.height + SIZES.takeGap) });
    });
    const headerDepth = SIZES.header.height + runs.length * (SIZES.run.height + SIZES.takeGap);
    const shots = nodes
      .filter((node) => node.type === "shot" && node.scene === scene.scene)
      .sort((a, b) => (a.type === "shot" && b.type === "shot" ? a.data.order - b.data.order : 0));
    // A long scene wraps: each line is as tall as its deepest stack of takes.
    let lineTop = y;
    for (let start = 0; start < Math.max(shots.length, 1); start += perRow) {
      const line = shots.slice(start, start + perRow);
      let deepest = 0;
      line.forEach((shot, column) => {
        const x = SIZES.header.width + SIZES.gap + column * (SIZES.shot.width + SIZES.gap);
        positions.set(shot.id, { x, y: lineTop });
        if (!showTakes || shot.type !== "shot") return;
        const takes = nodes.filter(
          (node) => node.type === "take" && node.scene === scene.scene && node.data.shot === shot.data.shot,
        );
        takes.forEach((take, row) => {
          positions.set(take.id, {
            x: x + (SIZES.shot.width - SIZES.take.width) / 2,
            y: lineTop + SIZES.shot.height + SIZES.takeGap + row * SIZES.takeStep,
          });
        });
        deepest = Math.max(deepest, takes.length);
      });
      const takesDepth = deepest ? SIZES.takeGap + (deepest - 1) * SIZES.takeStep + SIZES.take.height : 0;
      lineTop += SIZES.shot.height + takesDepth + SIZES.gap;
    }
    y = Math.max(y + headerDepth, lineTop - SIZES.gap) + SIZES.rowGap;
  }
  return positions;
}
