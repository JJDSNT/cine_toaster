// Where the film stands, phase by phase (the director's request, Demo 01, 2026-10-17):
// what we did, what is happening, what waits for them, and what comes next.
// A read-only view of /api/progress, which derives every phase from the film's records.
import { useEffect, useState } from "react";
import { request } from "./creation.ts";
import "./progress.css";

interface Phase { id: string; label: string; state: "done" | "active" | "waiting_you" | "next" | "later" | "blocked" | "skipped"; summary: string; url: string }
interface Progress {
  phases: Phase[]; current: string; now: string; next: string;
  you: { text: string; url: string; kind: string };
  jobs: { active: number; running: number; queued: number; failed: number; eta_minutes: number };
}

const MARK: Record<Phase["state"], string> = { done: "✓", active: "●", waiting_you: "!", next: "○", later: "○", blocked: "×", skipped: "–" };
const SAID: Record<Phase["state"], string> = {
  done: "done", active: "in progress", waiting_you: "waiting for you", next: "next", later: "later", blocked: "blocked", skipped: "not needed",
};

export function ProductionProgress() {
  const [data, setData] = useState<Progress | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    const refresh = () => request<Progress>("/api/progress", undefined, controller.signal)
      .then((value) => { setData(value); setFailed(false); })
      .catch(() => { if (!controller.signal.aborted) setFailed(true); });
    void refresh();
    // Faster while something is generating, so progress is seen without reloading.
    const timer = window.setInterval(() => { if (!document.hidden) void refresh(); }, 5000);
    return () => { controller.abort(); clearInterval(timer); };
  }, []);
  if (!data) return failed ? <p className="progress-failed" role="status">Progress unavailable: the records could not be read.</p> : null;
  return <section className="progress" aria-label="Production progress">
    <ol className="progress-phases">
      {data.phases.map((phase) => <li key={phase.id} className={`progress-phase is-${phase.state}`}
        aria-current={phase.id === data.current ? "step" : undefined}>
        <span className="progress-mark" aria-hidden="true">{MARK[phase.state]}</span>
        <span className="progress-label">{phase.url ? <a href={phase.url}>{phase.label}</a> : phase.label}</span>
        <span className="progress-state">{SAID[phase.state]}</span>
        <span className="progress-summary">{phase.summary}</span>
      </li>)}
    </ol>
    <dl className="progress-lines">
      <div><dt>Now</dt><dd>{data.now}{data.jobs.failed ? ` ${data.jobs.failed} picture(s) refused by the image model; the AI re-plans them.` : ""}</dd></div>
      <div className={data.you.url ? "is-yours" : ""}><dt>You</dt>
        <dd>{data.you.url ? <a href={data.you.url}>{data.you.text}</a> : data.you.text}</dd></div>
      {data.next && <div><dt>Then</dt><dd>{data.next}</dd></div>}
    </dl>
  </section>;
}
