// The directing assistant (ADR 0017, ADR 0018). The same component serves the
// canvas and, inside a drawer, every room of the control room.
//
// The page tells the agent what the person is looking at (useAgentContext).
// The agent can point at a shot and take the screen somewhere (shared state:
// that only moves the view). Inception appends scoped candidates/assessments;
// consequential production actions and human gates remain explicit decisions.
import { useEffect, useRef, useState } from "react";
import { CopilotChat, CopilotKitProvider, useAgent, useAgentContext, useCopilotKit, useInterrupt } from "@copilotkit/react-core/v2";
import "@copilotkit/react-core/v2/styles.css";

export interface Seen {
  room: string;
  scene: string;
  focus: string;
  selected: string;
  /** Anything else the room shows that matters: an open gate, the takes compared… */
  details?: string;
}

import type { Navigation } from "./navigation.ts";
export type { Navigation };

interface Shared {
  highlight?: string;
  navigate?: Navigation;
  agent_status?: { role: string; state: string; detail?: string };
  production_update?: { id: string; revision: number; kind: string };
}

const activityLabels: Record<string, string> = {
  working: "Working", needs_direction: "Awaiting your direction", needs_review: "Awaiting your review",
  blocked: "Unable to continue", resource_limit: "Turn limit reached", complete: "Complete",
  paused: "Paused", awaiting_confirmation: "Awaiting confirmation",
  waiting_for_job: "Generation running · continuation needed after completion",
};

const roleLabels: Record<string, string> = {
  coordinator: "Production Coordinator", inception: "Inception",
  art_direction: "Art Direction", visual_prevalidation: "Visual Prevalidation",
  directing: "Directing / Shot Planning", continuity: "Script Supervisor / Continuity",
};

/** One conversation per browser tab, kept across rooms and pages. */
function threadId(): string {
  const key = "cine-toaster:assistant-thread";
  try {
    const known = sessionStorage.getItem(key);
    if (known) return known;
    const made = `thread-${Math.random().toString(36).slice(2, 10)}`;
    sessionStorage.setItem(key, made);
    return made;
  } catch {
    return "thread-default";
  }
}

const FOLLOWED = "cine-toaster:assistant-navigated";

function followed(requestId: string): boolean {
  try { return (sessionStorage.getItem(FOLLOWED) || "").split(" ").includes(requestId); } catch { return false; }
}

function remember(requestId: string): void {
  try {
    const known = (sessionStorage.getItem(FOLLOWED) || "").split(" ").filter(Boolean).slice(-50);
    sessionStorage.setItem(FOLLOWED, [...known, requestId].join(" "));
  } catch { /* storage unavailable: at worst a request is followed twice */ }
}

function readMessage(value: unknown): string {
  if (typeof value === "string") {
    try { return readMessage(JSON.parse(value)); } catch { return value; }
  }
  if (value && typeof value === "object" && "message" in value) return String((value as { message: unknown }).message);
  return "";
}

interface Props {
  seen: Seen;
  onHighlight: (shot: string) => void;
  onNavigate?: (where: Navigation) => void;
  continuation?: { decisionId: string; attempt?: string } | null;
  onProductionUpdate?: () => void;
}

function Conversation({ seen, onHighlight, onNavigate, onProductionUpdate, continuation, thread }: Props & { thread: string }) {
  useAgentContext({ description: "Current room", value: seen.room });
  useAgentContext({ description: "Current scene id", value: seen.scene });
  useAgentContext({ description: "What the room shows", value: seen.focus });
  useAgentContext({ description: "Selected", value: seen.selected || "nothing" });
  useAgentContext({ description: "Also on screen", value: seen.details || "nothing else" });
  const { agent, isReady } = useAgent({ agentId: "assistant" });
  const { copilotkit } = useCopilotKit();
  const [continuationError, setContinuationError] = useState("");
  const continued = useRef(new Set<string>());
  const refreshed = useRef("");
  const shared = (agent?.state ?? {}) as Shared;
  const update = shared.production_update;
  useEffect(() => {
    if (update?.id && refreshed.current !== update.id) {
      refreshed.current = update.id;
      onProductionUpdate?.(); // refresh authoritative application records; this is not a telemetry bus
    }
  }, [update, onProductionUpdate]);
  const running = agent?.isRunning;
  useEffect(() => {
    const id = continuation?.decisionId;
    const intent = id + (continuation?.attempt ? "-" + continuation.attempt : "");
    if (!id || !agent || !isReady || running || continued.current.has(intent)) return;
    continued.current.add(intent);
    setContinuationError("");
    agent.threadId = thread;
    // This is a human-originated CoAgent interaction, not a second dispatcher.
    // `resume` is typed state bound to this one message (ADR 0034); the graph
    // resolves the decision from production records before using it.
    const message = `decision-${intent}`;
    agent.setState({ ...(agent.state ?? {}), resume: { decision: id, message } });
    agent.addMessage({ id: message, role: "user",
      content: "Continue from the direction I just recorded. Read the saved decision and its scope before acting." });
    void copilotkit.runAgent({ agent }).catch((error: unknown) => {
      setContinuationError(`The decision was saved, but continuation failed: ${String(error)}. Ask the assistant to continue when available.`);
    });
  }, [continuation, agent, isReady, running, copilotkit, thread]);
  const highlight = shared.highlight ?? "";
  useEffect(() => onHighlight(highlight), [highlight, onHighlight]);
  // Move the screen once per request. Requests already followed are remembered
  // for the tab, so a page opened by one (the thread is shared) does not follow
  // it again.
  const where = shared.navigate;
  useEffect(() => {
    if (!where?.id || followed(where.id)) return;
    remember(where.id);
    onNavigate?.(where);
  }, [where, onNavigate]);
  useInterrupt({
    agentId: "assistant",
    render: (props) => {
      const { resolve } = props;
      const standard = (props as { interrupt?: { message?: string } }).interrupt;
      const message = standard?.message || readMessage((props as { event?: { value?: unknown } }).event?.value) || "Confirmar?";
      return (
        <div className="assistant-confirm" data-testid="assistant-confirm">
          <p>{message}</p>
          <button type="button" onClick={() => resolve({ approved: true })}>Sim</button>
          <button type="button" onClick={() => resolve({ approved: false })}>Não</button>
        </div>
      );
    },
  });
  return <><p className="assistant-role" role="status" data-testid="assistant-role">
    {shared.agent_status ? `${roleLabels[shared.agent_status.role] || shared.agent_status.role} · ${activityLabels[shared.agent_status.state] || "Status unavailable"}`
      : "Production Coordinator"}
  </p>{continuationError && <p role="alert">{continuationError}</p>}
    <CopilotChat agentId="assistant" threadId={thread} /></>;
}

export default function Assistant(props: Props) {
  const thread = useRef(threadId()).current;
  return (
    // The development inspector fetches from outside the machine (CT-0043): off.
    <CopilotKitProvider runtimeUrl="/api/copilotkit" enableInspector={false}>
      <Conversation {...props} thread={thread} />
    </CopilotKitProvider>
  );
}
