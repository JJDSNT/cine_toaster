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
  revision: number;
  /** The location the scene is set in, and its plates by camera (SPEC-0010). */
  location: string;
  plates: { camera: string; path: string }[];
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
  /** The generation block the shot belongs to, if any. */
  block: string;
  findings: number;
  severity: Severity;
  /** The shot's number as the breakdown writes it: what a lineage names. */
  number: string;
  /** What the picture is made from, and whose faces a derived one takes (CT-0046). */
  from: string[];
  derived: boolean;
  with: string[];
  reference_decided: boolean;
  /** What the breakdown says, when a decision stands over it. */
  authored_from: string[];
  authored_with: string[];
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

export interface RunStep {
  label: string;
  state: "pending" | "running" | "waiting" | "done" | "skipped" | "failed";
  kind: string;
}

/** The latest workflow run of a block (SPEC-0009). */
export interface RunData {
  scene: string;
  run: string;
  block: string;
  /** A single shot's run, when it is not a block's. */
  shot: string;
  state: "running" | "waiting" | "done" | "failed" | "cancelled";
  steps: RunStep[];
  /** The step waiting for a person, if any. */
  waiting: string;
}

export type GraphNode =
  | { id: string; type: "scene"; scene: string; data: SceneData }
  | { id: string; type: "shot"; scene: string; data: ShotData }
  | { id: string; type: "take"; scene: string; data: TakeData }
  | { id: string; type: "run"; scene: string; data: RunData };

export interface CutData {
  cut: string;
  chain: string;
  reason: string;
  transition: string;
  transition_ms: number;
  transition_reason: string;
  findings: string[];
  severity: Severity;
  /** Decided in the runtime over the breakdown (plan step 13). */
  decided: boolean;
  /** What the breakdown says, when a decision stands over it. */
  authored: string;
  /** The scene's revision this edge was drawn from. */
  revision: number;
}

export type GraphEdge =
  | { id: string; type: "cut"; source: string; target: string; data: CutData }
  | { id: string; type: "take"; source: string; target: string; data: { selected: boolean } }
  | { id: string; type: "scene-order"; source: string; target: string; data: Record<string, never> }
  | { id: string; type: "run"; source: string; target: string; data: { state: string } }
  | { id: string; type: "lineage"; source: string; target: string; data: { relation: string; decided: boolean } };

export interface Sequence {
  id: string;
  label: string;
  scenes: string[];
}

export interface ProductionGraph {
  production: { id: string; title: string; active_scene: string; sequences: Sequence[]; cast: { id: string; label: string }[] };
  nodes: GraphNode[];
  edges: GraphEdge[];
}
