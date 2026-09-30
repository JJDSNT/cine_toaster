// The directing assistant beside the canvas (ADR 0017, ADR 0018). Loaded only
// when the runtime says the assistant is on, so the canvas stays light.
//
// The page tells the agent what the person is looking at (useAgentContext);
// the agent can point at a shot (shared state), and asks here before it acts.
import { useEffect } from "react";
import { CopilotChat, CopilotKitProvider, useAgent, useAgentContext, useInterrupt } from "@copilotkit/react-core/v2";
import "@copilotkit/react-core/v2/styles.css";

export interface Seen {
  room: string;
  scene: string;
  focus: string;
  selected: string;
}

function readMessage(value: unknown): string {
  if (typeof value === "string") {
    try { return readMessage(JSON.parse(value)); } catch { return value; }
  }
  if (value && typeof value === "object" && "message" in value) return String((value as { message: unknown }).message);
  return "";
}

function Conversation({ seen, onHighlight }: { seen: Seen; onHighlight: (shot: string) => void }) {
  useAgentContext({ description: "Current room", value: seen.room });
  useAgentContext({ description: "Current scene id", value: seen.scene });
  useAgentContext({ description: "What the canvas shows", value: seen.focus });
  useAgentContext({ description: "Selected", value: seen.selected || "nothing" });
  const { agent } = useAgent({ agentId: "assistant" });
  const highlight = (agent?.state as { highlight?: string } | undefined)?.highlight ?? "";
  useEffect(() => onHighlight(highlight), [highlight, onHighlight]);
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
  return <CopilotChat agentId="assistant" />;
}

export default function Assistant(props: { seen: Seen; onHighlight: (shot: string) => void }) {
  return (
    // The development inspector fetches from outside the machine (CT-0043): off.
    <CopilotKitProvider runtimeUrl="/api/copilotkit" enableInspector={false}>
      <Conversation {...props} />
    </CopilotKitProvider>
  );
}
