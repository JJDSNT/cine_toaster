export interface AgentWork {
  id: string; state: string; instruction: string; url: string;
  kind?: string; title?: string; owner?: string; sequence?: string; sequence_label?: string;
  scene_ids?: string[]; current_scene_ids?: string[]; scope_changed?: boolean; sources_changed?: boolean;
  dispatch_status?: string; next_action?: string; review_roles?: string[];
  human_action_required?: boolean; execution_supported?: boolean;
  coverage?: { shots: number; shots_with_records: number; meaning: string };
  gaps?: { code: string; owner: string; description: string; next_action: string }[];
  outputs?: { id: string; scene: string; shot: string; url: string }[];
}

export function workScope(item: AgentWork): string {
  if (!item.sequence) return "";
  const scenes = item.current_scene_ids ?? item.scene_ids ?? [];
  return `${item.sequence_label ?? item.sequence} · ${scenes.length} scenes${item.coverage ? ` · ${item.coverage.shots} shots` : ""}`;
}

export function workState(item: AgentWork): string {
  return item.state === "pending_agent" ? "Pending AI work" : item.state.replaceAll("_", " ");
}
