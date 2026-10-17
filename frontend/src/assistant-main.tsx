// The assistant as a drawer inside the control room: an iframe on the same
// origin. The room posts what is on screen; this posts back where to point and
// where to go. Keeping React and CopilotKit here leaves the control room as it is.
import { StrictMode, useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import Assistant, { type Continuation, type Navigation, type Seen } from "./Assistant.tsx";
import "./styles.css";

const EMPTY: Seen = { room: "control room", scene: "", focus: "", selected: "" };

function Drawer() {
  const [seen, setSeen] = useState<Seen>(EMPTY);
  const [continuation, setContinuation] = useState<Continuation | null>(null);
  useEffect(() => {
    const listen = (event: MessageEvent) => {
      if (event.origin !== window.location.origin || event.source !== window.parent) return;
      if (event.data?.type === "cine-toaster:context") setSeen({ ...EMPTY, ...event.data.seen });
      if (event.data?.type === "cine-toaster:continue-inception" && typeof event.data.decisionId === "string")
        setContinuation({ decisionId: event.data.decisionId, attempt: typeof event.data.attempt === "string" ? event.data.attempt : undefined });
      if (event.data?.type === "cine-toaster:continue-inception" && typeof event.data.intake === "string")
        setContinuation({ intake: event.data.intake });
    };
    window.addEventListener("message", listen);
    window.parent.postMessage({ type: "cine-toaster:assistant-ready" }, window.location.origin);
    return () => window.removeEventListener("message", listen);
  }, []);
  const onHighlight = useCallback((shot: string) => {
    window.parent.postMessage({ type: "cine-toaster:highlight", shot }, window.location.origin);
  }, []);
  const onNavigate = useCallback((where: Navigation) => {
    window.parent.postMessage({ type: "cine-toaster:navigate", where }, window.location.origin);
  }, []);
  const onProductionUpdate = useCallback(() => {
    window.parent.postMessage({ type: "cine-toaster:production-update" }, window.location.origin);
  }, []);
  return (
    <div className="assistant-drawer dark">
      <Assistant seen={seen} onHighlight={onHighlight} onNavigate={onNavigate}
        continuation={continuation} onProductionUpdate={onProductionUpdate} />
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<StrictMode><Drawer /></StrictMode>);
