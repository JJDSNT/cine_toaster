// The assistant as a drawer inside the control room: an iframe on the same
// origin. The room posts what is on screen; this posts back where to point and
// where to go. Keeping React and CopilotKit here leaves the control room as it is.
import { StrictMode, useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import Assistant, { type Navigation, type Seen } from "./Assistant.tsx";
import "./styles.css";

const EMPTY: Seen = { room: "control room", scene: "", focus: "", selected: "" };

function Drawer() {
  const [seen, setSeen] = useState<Seen>(EMPTY);
  useEffect(() => {
    const listen = (event: MessageEvent) => {
      if (event.origin !== window.location.origin || event.data?.type !== "cine-toaster:context") return;
      setSeen({ ...EMPTY, ...event.data.seen });
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
  return (
    <div className="assistant-drawer dark">
      <Assistant seen={seen} onHighlight={onHighlight} onNavigate={onNavigate} />
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<StrictMode><Drawer /></StrictMode>);
