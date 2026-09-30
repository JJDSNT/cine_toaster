// The directing assistant (ADR 0017, ADR 0018). The same component serves the
// canvas and, inside a drawer, every room of the control room.
//
// The page tells the agent what the person is looking at (useAgentContext).
// The agent can point at a shot and take the screen somewhere (shared state:
// that only moves the view), and asks here before it changes the film.
import { useEffect, useRef } from "react";
import { CopilotChat, CopilotKitProvider, useAgent, useAgentContext, useInterrupt } from "@copilotkit/react-core/v2";
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
}

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
}

function Conversation({ seen, onHighlight, onNavigate, thread }: Props & { thread: string }) {
  useAgentContext({ description: "Current room", value: seen.room });
  useAgentContext({ description: "Current scene id", value: seen.scene });
  useAgentContext({ description: "What the room shows", value: seen.focus });
  useAgentContext({ description: "Selected", value: seen.selected || "nothing" });
  useAgentContext({ description: "Also on screen", value: seen.details || "nothing else" });
  const { agent } = useAgent({ agentId: "assistant" });
  const shared = (agent?.state ?? {}) as Shared;
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
  return <CopilotChat agentId="assistant" threadId={thread} />;
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
