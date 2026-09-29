// The shape `GET /api/graph` returns (cine_toaster/graph.py). The canvas only
// reads it: every change to the film goes through the runtime's commands.

export type Severity = "" | "advice" | "warning" | "error";

export interface Picture {
  level: "still" | "take" | "blocking" | "none";
  image?: string;
  video?: string;
}

export interface SceneData {
  scene: string;
  title: string;
  order: number;
  sequence: string;
  status: string;
  findings: number;
  severity: Severity;
}

export interface ShotData {
  scene: string;
  shot: string;
  order: number;
  label: string;
  camera: string;
  duration_seconds: number;
  status: string;
  source: string;
  selected_take: string;
  takes: number;
  speakers: string[];
  move: string;
  walks: boolean;
  picture: Picture;
  findings: number;
  severity: Severity;
}

export interface TakeData {
  scene: string;
  shot: string;
  take: string;
  label: string;
  status: string;
  selected: boolean;
  media: string;
  poster: string;
}

export type GraphNode =
  | { id: string; type: "scene"; scene: string; data: SceneData }
  | { id: string; type: "shot"; scene: string; data: ShotData }
  | { id: string; type: "take"; scene: string; data: TakeData };

export interface CutData {
  cut: string;
  chain: string;
  reason: string;
  transition: string;
  findings: string[];
  severity: Severity;
}

export type GraphEdge =
  | { id: string; type: "cut"; source: string; target: string; data: CutData }
  | { id: string; type: "take"; source: string; target: string; data: { selected: boolean } }
  | { id: string; type: "scene-order"; source: string; target: string; data: Record<string, never> };

export interface ProductionGraph {
  production: { id: string; title: string };
  nodes: GraphNode[];
  edges: GraphEdge[];
}
