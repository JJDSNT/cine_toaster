import { createRoot } from "react-dom/client";
import { useState } from "react";
import { CopilotKitProvider, CopilotChat, useAgent, useAgentContext, useInterrupt } from "@copilotkit/react-core/v2";
import "@copilotkit/react-core/v2/styles.css";

const SHOTS = [
  { id: "P1", label: "The stack lights one channel at a time" },
  { id: "P2", label: "Mara crosses the room" },
  { id: "P3", label: "Locked on Mara as the station repeats her words" },
];

function Room() {
  const [selected, setSelected] = useState("P2");
  // What the director is looking at: the agent receives this with every turn.
  useAgentContext({ description: "Current scene id", value: "SC-030" });
  useAgentContext({ description: "Current room", value: "scene room of SC-030 (Echo Chamber)" });
  useAgentContext({ description: "Selected shot", value: `${selected}: ${SHOTS.find((s) => s.id === selected)?.label}` });
  useAgentContext({ description: "Generation blocks", value: "block A = P2 + P3; P3's master picture is derived from a render with MARA's face; no workflow run yet" });
  // State the agent shares with the page.
  const { agent } = useAgent({ agentId: "director" });
  const highlight = (agent?.state as { highlight?: string } | undefined)?.highlight ?? "";
  // The agent asks before acting: its question is rendered here, in the chat.
  useInterrupt({
    agentId: "director",
    render: ({ event, resolve }) => {
      const value = (event?.value ?? {}) as { message?: string };
      return (
        <div data-testid="confirm" style={{ border: "1px solid #e7b75c", padding: 10, borderRadius: 8 }}>
          <p>{value.message ?? "Confirm?"}</p>
          <button onClick={() => resolve({ approved: true })}>Sim, iniciar</button>{" "}
          <button onClick={() => resolve({ approved: false })}>Não</button>
        </div>
      );
    },
  });
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 420px", height: "100vh" }}>
      <div style={{ padding: 24 }}>
        <h2>SC-030 · Echo Chamber</h2>
        {SHOTS.map((shot) => (
          <div key={shot.id} data-shot={shot.id} onClick={() => setSelected(shot.id)}
               style={{ padding: 12, margin: "8px 0", borderRadius: 8, cursor: "pointer",
                        border: `2px solid ${highlight === shot.id ? "#ef6a3a" : selected === shot.id ? "#70aee8" : "#2b3134"}` }}>
            <strong>{shot.id}</strong> {shot.label} {highlight === shot.id && <em data-testid="highlight">← the assistant</em>}
          </div>
        ))}
        <pre data-testid="state" style={{ fontSize: 11, color: "#8c9597" }}>{JSON.stringify(agent?.state ?? {}, null, 1)}</pre>
      </div>
      <CopilotChat agentId="director" />
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <CopilotKitProvider runtimeUrl="/api/copilotkit" enableInspector={false}><Room /></CopilotKitProvider>,
);
