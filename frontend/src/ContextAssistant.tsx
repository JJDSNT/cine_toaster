import { useEffect, useRef, useState } from "react";
import { addressOf, type Navigation } from "./navigation.ts";
import type { Continuation, Seen } from "./Assistant.tsx";

export function ContextAssistant({ seen, continuation, onRecordsChanged }: {
  seen: Seen; continuation?: Continuation | null; onRecordsChanged?: () => void;
}) {
  const [state, setState] = useState("checking");
  const [open, setOpen] = useState(true);
  const [ready, setReady] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const frame = useRef<HTMLIFrameElement>(null);
  const changed = useRef(onRecordsChanged);
  changed.current = onRecordsChanged;
  useEffect(() => { if (continuation) setOpen(true); }, [continuation]);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/copilotkit/info", { signal: controller.signal }).then(async (response) => {
      const data = await response.json().catch(() => null);
      if (!controller.signal.aborted) setState(response.ok ? "available" : data?.error?.code === "assistant_off" ? "off" : "unavailable");
    }).catch(() => { if (!controller.signal.aborted) setState("unavailable"); });
    return () => controller.abort();
  }, [refresh]);
  useEffect(() => {
    const receive = (event: MessageEvent) => {
      if (event.origin !== window.location.origin || event.source !== frame.current?.contentWindow) return;
      if (event.data?.type === "cine-toaster:assistant-ready") setReady(true);
      if (event.data?.type === "cine-toaster:production-update") changed.current?.();
      if (event.data?.type === "cine-toaster:navigate" && event.data.where) window.location.assign(addressOf(event.data.where as Navigation));
    };
    window.addEventListener("message", receive);
    return () => window.removeEventListener("message", receive);
  }, []);
  useEffect(() => {
    if (ready && open) frame.current?.contentWindow?.postMessage({ type: "cine-toaster:context", seen }, window.location.origin);
  }, [seen, ready, open]);
  useEffect(() => {
    if (ready && open && continuation) frame.current?.contentWindow?.postMessage({
      type: "cine-toaster:continue-inception", ...continuation,
    }, window.location.origin);
  }, [continuation, ready, open]);
  return <aside className={`prep-assistant creation-assistant ${open ? "" : "collapsed"}`} aria-label="Creative assistant">
    <div className="prep-section-heading"><h2>Assistant · {state}</h2>
      <button aria-expanded={open} onClick={() => { setOpen(!open); setReady(false); }}>{open ? "Collapse" : "Open"}</button></div>
    {open && (state === "available" ? <iframe ref={frame} title="Creative assistant" src="/app/assistant.html" onLoad={() => setReady(true)} />
      : <><p role="status">{state === "off" ? "The assistant is off for this session." : state === "checking" ? "Checking availability…" : "The assistant service could not be reached."}</p>
        <p>Drafts and references remain available. Launch with <code>toast serve &lt;film&gt; --assistant</code> to enable chat.</p>
        <button onClick={() => setRefresh((n) => n + 1)}>Check again</button></>)}
  </aside>;
}
