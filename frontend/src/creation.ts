export interface Input { kind: "concept" | "reference"; id: string; sha256: string; title?: string; files?: Record<string, string> }
export interface Draft {
  id: string; kind: "concept" | "screenplay"; title: string; text: string; based_on: string;
  inputs: Input[]; created_at: string; rationale: string;
}
export interface Reference {
  id: string; title: string; images: string[]; prompt?: string; notes?: string | string[]; from?: string[];
  findings: { severity: string; message: string }[];
  director_on_the_prompt?: string[];
}
export interface ReferenceHistoryNode {
  id: string; title: string; depth: number; review: string;
  parents: { id: string; evidence: string }[];
  uses: { kind: string; id: string; title: string; evidence: string; scene?: string; shot?: string }[];
  sources: { kind: string; id: string }[]; related: string[];
  selections: { kind: string; id: string; role: string; purpose: string }[];
  rounds: { id: string; title: string }[];
  corrects: { id: string; round: string; reason: string }[];
  revised_by: { id: string; round: string; reason: string }[];
}
export interface ExplorationRound {
  id: string; title: string; references: Input[]; follows: string; rationale: string; source: string;
  corrections: { previous: string; current: string }[]; created_at: string;
  round_id?: string; based_on?: string; version?: number;
}
export interface CreationState {
  title: string; revision: number; drafts: Draft[]; references: Reference[];
  rounds: ExplorationRound[];
  active_rounds: ExplorationRound[];
  storyboard_uses?: Record<string, { scene: string; shot: string; board: string; version?: number; order: number }[]>;
  findings: { draft: string; input: string; message: string }[];
  reference_history: { nodes: ReferenceHistoryNode[]; summary: { retained: number; reused: number; provider_input_links: number; cast_selections: number; review: string } };
  inception_review?: InceptionReviewState;
  art_direction?: { briefs: ArtBrief[]; reviews: VisualReview[] };
  directing?: { plans: DirectionPlan[]; reviews: ContinuityReview[] };
  handoffs?: StageHandoff[];
}
export interface StageHandoff {
  id: string; decision: string; destination: string; target: HandoffTarget;
  coverage?: { shots: number; drawn: number }; missing?: { scene: string; shot: string }[];
  scope: string; instruction: string; stale: boolean;
  outputs: { id: string; scene: string; shot: string; url: string }[];
}
export interface DirectionPlan {
  id: string; scene: string; title: string; intention: string; based_on: string; stale: boolean;
  shots: { id: string; label: string; action: string; framing: string; camera_intent: string;
    duration_seconds: number; script_units: number[]; existing_shot?: string; transition_intent?: string;
    state_in: { subject: string; attribute: string; value: string }[];
    state_out: { subject: string; attribute: string; value: string }[] }[];
  checks: { code: string; severity: string; evidence: string }[];
}
export interface ContinuityReview {
  id: string; scene: string; plan: string; verdict: string; summary: string; stale: boolean;
  findings: { basis: string; severity: string; evidence: string; correction: string; sources: string[] }[];
  limitations: string[]; checks: { code: string; severity: string; evidence?: string; message?: string }[];
  canonical_checks: { code: string; severity: string; evidence?: string; message?: string }[];
}
export interface ArtBrief { id: string; title: string; text: string; criteria: string[]; based_on: string; inputs: Input[] }
export interface VisualReview {
  id: string; brief: string; verdict: "ready_for_human" | "needs_changes" | "inconclusive";
  summary: string; stale: boolean; human_approval: false;
  findings: { criterion: string; status: string; evidence: string; correction: string }[];
  images: { reference: string; file: string; sha256: string }[];
}
export interface InceptionAssessment {
  id: string; title: string; summary: string; status: "awaiting_decision" | "approved" | "changes_requested" | "needs_reassessment";
  material_changed: boolean;
  readiness: { destination: string; status: "ready" | "needs_work" | "not_assessed"; summary: string;
    gaps: { description: string; owner: string; next_action: string }[] }[];
  proposal: { destination: string; question: string; scope: string; why: string; next_step: string; direction_plan?: string; continuity_review?: string; review_kind?: string };
  decision: { id: string; outcome: string; guidance: string } | null;
  handoff_preview?: { can_advance: boolean; target: HandoffTarget | null; sha256: string };
  next_agent_action: { instruction: string; status: string; owner: string } | null;
}
export interface InceptionReviewState { current: InceptionAssessment | null; history: unknown[]; decisions: unknown[] }
export async function request<T>(url: string, payload?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, payload === undefined ? { signal } : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload), signal,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error?.message ?? `HTTP ${response.status}`);
  return data as T;
}
export function candidateAddress(id: string): string {
  return `/app/preproduction.html?draft=${encodeURIComponent(id)}`;
}
export function conceptOf(draft: Draft): string {
  return draft.inputs.find((item) => item.kind === "concept")?.id ?? "";
}

export function referenceGroups(data: CreationState) {
  const known = new Map(data.references.map((item) => [item.id, item]));
  const assigned = new Set<string>();
  const groups: { id: string; title: string; number: number | null; round: ExplorationRound | null; references: Reference[];
                  missing: string[]; storyboard?: boolean }[] = (data.active_rounds ?? data.rounds).map((round, index) => {
    round.references.forEach((ref) => assigned.add(ref.id));
    return { id: round.id, title: round.title, number: index + 1, round,
      references: round.references.map((ref) => known.get(ref.id)).filter((ref): ref is Reference => Boolean(ref)),
      missing: round.references.filter((ref) => !known.has(ref.id)).map((ref) => ref.id) };
  });
  const uses = data.storyboard_uses ?? {};
  // Storyboard drawings are filed apart, in scene/shot order, not mixed into "Unassigned" (Demo 01).
  const drawings = data.references.filter((item) => !assigned.has(item.id) && uses[item.id]?.length)
    .sort((a, b) => {
      const [x, y] = [uses[a.id][0], uses[b.id][0]];
      return x.order - y.order || x.shot.localeCompare(y.shot, undefined, { numeric: true });
    });
  const unassigned = data.references.filter((item) => !assigned.has(item.id) && !uses[item.id]?.length);
  if (unassigned.length) groups.push({ id: "unassigned", title: groups.length ? "Unassigned references" : "References",
    number: null, round: null, references: unassigned, missing: [] });
  if (drawings.length) groups.push({ id: "storyboard", title: "Storyboard drawings", number: null, round: null,
    references: drawings, missing: [], storyboard: true });
  return groups;
}

/** One scene's shots, or a whole canonical sequence: the director's unit of review (ADR 0035). */
export type HandoffTarget =
  | { scene: string; shots: string[] }
  | { sequence: string; label?: string; scenes: { scene: string; shots: string[] }[] };

export function targetLabel(target: HandoffTarget): string {
  if ("sequence" in target) {
    const shots = target.scenes.reduce((total, part) => total + part.shots.length, 0);
    return `${target.label || target.sequence}: ${target.scenes.length} scenes, ${shots} shots, in order`;
  }
  return `${target.scene} / ${target.shots.join(", ")}`;
}

export function targetShotCount(target: HandoffTarget): number {
  return "sequence" in target ? target.scenes.reduce((total, part) => total + part.shots.length, 0) : target.shots.length;
}
