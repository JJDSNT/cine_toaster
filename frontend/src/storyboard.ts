export interface StoryDrawing {
  id: string; scene: string; shot: string; title: string; version: number; based_on: string; note: string;
  image: { path: string; sha256: string }; image_available: boolean; review: string;
  inputs: { id: string; sha256: string; title?: string }[];
  findings: { code: string; message: string }[]; provenance: Record<string, unknown>;
}
export interface StoryDrawings {
  revision: number; candidates: StoryDrawing[];
  coverage: { scene: string; shots: number; with_candidates: number }[];
}
export function drawingVersions(data: StoryDrawings | null, scene: string, shot: string): StoryDrawing[] {
  return (data?.candidates ?? []).filter((item) => item.scene === scene && item.shot === shot).slice().reverse();
}
export function drawingPreview(versions: StoryDrawing[], candidate: string): StoryDrawing | undefined {
  return candidate ? versions.find((item) => item.id === candidate) : versions[0];
}
