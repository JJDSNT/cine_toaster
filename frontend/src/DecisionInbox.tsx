import { useEffect, useState } from "react";
import { request, type CreationState } from "./creation.ts";
import { InceptionReview } from "./InceptionReview.tsx";
import { ContextAssistant } from "./ContextAssistant.tsx";
import type { Continuation } from "./Assistant.tsx";
import "./decisions.css";
import { ProductionProgress } from "./ProductionProgress.tsx";
import { workScope, workState, type AgentWork } from "./productionWork.ts";

interface Inbox {
  pending_count: number; agent_work_count?: number; coverage: string;
  items: { id: string; kind: string; question: string; scope: string; why: string; next_step: string; url: string }[];
  agent_work: AgentWork[];
}

export function DecisionLink() {
  const [count, setCount] = useState<number | null>(null);
  const [failed, setFailed] = useState(false);
  const [workCount, setWorkCount] = useState<number | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    const refresh = () => request<Inbox>("/api/decisions", undefined, controller.signal)
      .then((value) => { setCount(value.pending_count); setWorkCount(value.agent_work_count ?? 0); setFailed(false); })
      .catch(() => { if (!controller.signal.aborted) setFailed(true); });
    void refresh();
    const timer = window.setInterval(() => { if (!document.hidden) void refresh(); }, 15000);
    return () => { controller.abort(); clearInterval(timer); };
  }, []);
  return <><a className="decision-link" href="/app/decisions.html">Awaiting you · {failed ? "unavailable" : count ?? "…"}</a>
    <a className="decision-link" href="/app/decisions.html#agent-work">AI work · {failed ? "unavailable" : workCount ?? "…"}</a></>;
}

/** One interview question, answered in the person's own words (SPEC-0020). */
function IntakeAnswer({ item, revision, onAnswered }: {
  item: Inbox["items"][number]; revision: number; onAnswered: (answer: string, last: boolean) => Promise<void>;
}) {
  const [text, setText] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  async function save() {
    setSaving(true); setError("");
    try {
      const result = await request<{ answer: { id: string } }>("/api/creation/intake-answer",
        { question: item.id, answer: text, expected_revision: revision });
      const inbox = await request<Inbox>("/api/decisions");
      await onAnswered(result.answer.id, !inbox.items.some((other) => other.kind === "question"));
    } catch (reason) { setError(String(reason)); } finally { setSaving(false); }
  }
  return <section id="intake" aria-label="Interview question"><h3>{item.question}</h3>
    <p>Why it matters: {item.why}</p><p>Format: {item.scope}</p>
    <label>Your answer<textarea value={text} onChange={(event) => setText(event.target.value)} rows={3} /></label>
    <button disabled={saving || !text.trim()} onClick={() => void save()}>{saving ? "Saving…" : "Save answer"}</button>
    {error && <p role="alert">Not saved: {error}</p>}
    <p className="prep-help">{item.next_step} Your words are kept as they are; nothing is approved by answering.</p></section>;
}

export function DecisionInbox() {
  const [data, setData] = useState<Inbox | null>(null);
  const [creation, setCreation] = useState<CreationState | null>(null);
  const [error, setError] = useState("");
  const [continuation, setContinuation] = useState<Continuation | null>(null);
  const [work, setWork] = useState<AgentWork | null>(null);
  async function reload() {
    try {
      const [inbox, records] = await Promise.all([request<Inbox>("/api/decisions"), request<CreationState>("/api/creation")]);
      setData(inbox); setCreation(records); setError("");
    } catch (reason) { setError(String(reason)); }
  }
  useEffect(() => { void reload(); }, []);
  return <div className="prep-shell"><header className="prep-header"><div><h1>Awaiting you</h1>
    <p>{creation?.title ?? "Production decisions"} · Human decisions and AI work</p></div><button onClick={() => void reload()}>Refresh decisions</button></header>
    <nav className="prep-workspaces"><a href="/app/creation.html">Creation / Inception</a>
      <a href="/app/preproduction.html">Screenplay & Storyboard</a><a href="/">Control Room</a><a href="/app/">Canvas</a></nav>
    <ProductionProgress />
    <div className="prep-body"><main className="prep-work">
      {error && <p role="alert">Could not refresh decisions: {error}. A failed read does not mean there are no requests.</p>}
      {!data && !error && <p role="status">Reading production requests…</p>}
      {data && <><h2>{data.pending_count} pending decision{data.pending_count === 1 ? "" : "s"}</h2>
        <p className="prep-help">{data.coverage}</p>
        {!data.pending_count && <p>No saved human decision is waiting. Check next work below; this does not mean the film is finished.</p>}
        {data.items.map((item) => <article className="decision-item" key={item.id}>
          <a href={item.url}>Open request in context →</a>
          {item.kind === "direction" && creation?.inception_review?.current?.id === item.id ?
            <InceptionReview data={creation} title="Your decision" reload={reload}
              onDecision={(decisionId, attempt) => { setWork(null); setContinuation({ decisionId, attempt }); }} /> :
            item.kind === "question" && creation ?
            <IntakeAnswer item={item} revision={creation.revision} onAnswered={async (answer, last) => {
              await reload(); if (last) { setWork(null); setContinuation({ intake: answer }); } }} /> :
            <><h3>{item.question}</h3><p>Scope: {item.scope}</p><p>{item.why}</p><p>After your decision: {item.next_step}</p></>}
        </article>)}
        <section id="agent-work" aria-label="AI work"><h2>AI work & retained outputs</h2>
        <p>{data.agent_work_count ?? 0} pending AI task{data.agent_work_count === 1 ? "" : "s"}. These are not decisions waiting for your approval.</p>
        {data.agent_work.map((item) => <article className="decision-item" id={item.id} key={item.id}>
          <h3>{item.title ?? workState(item)}</h3>{item.title && <p>{workState(item)}</p>}
          {item.owner && <p>Owner: {item.owner === "coordinator" ? "Production Coordinator" : item.owner}</p>}
          {item.sequence && <><p>Scope: {workScope(item)}</p>
            <p>Ordered scenes: {(item.current_scene_ids ?? item.scene_ids ?? []).join(" → ") || "Canonical scope unavailable"}</p></>}
          {item.scope_changed && <p>Requested scenes: {item.scene_ids?.join(" → ")}. Canonical scope changed; refresh the request before review.</p>}
          {item.coverage && <p>{item.coverage.shots_with_records}/{item.coverage.shots} shots have drawing records. {item.coverage.meaning}</p>}
          <p>{item.instruction}</p>
          {item.dispatch_status === "not_dispatched" && <p>Not dispatched. No background agent run is claimed.</p>}
          {item.gaps?.length ? <><h4>Agent-owned gaps</h4><ul>{item.gaps.map((gap) => <li key={gap.code}>
            <p>{gap.description}</p><p>Owner: {gap.owner}. Next: {gap.next_action}</p></li>)}</ul></> : null}
          {item.next_action && <p>Next action: {item.next_action}</p>}
          {item.execution_supported === false && <p>The complete sequence review capability is not available yet. This task is not ready for human approval.</p>}
          {item.sequence ? <button onClick={() => { setContinuation(null); setWork(item); }}>Discuss this work with the copilot</button> : <a href={item.url}>Open material →</a>}
          {item.outputs?.map((output) => <p key={output.id}><a href={output.url}>Storyboard {output.scene} / {output.shot}</a></p>)}
        </article>)}</section>
        {creation && !data.pending_count && creation.inception_review?.current?.decision &&
          <InceptionReview data={creation} title="Latest direction & continuation" reload={reload}
            onDecision={(decisionId, attempt) => { setWork(null); setContinuation({ decisionId, attempt }); }} />}
      </>}
    </main>{(continuation || work) && <ContextAssistant continuation={continuation} onRecordsChanged={() => void reload()}
      seen={{ room: "decisions", scene: "", focus: "", selected: work?.id ?? "", details: work ?
        `Canonical agent work ${work.id}, sequence ${work.sequence}. Reread production_work; pending is not running or human approval.` :
        "Canonical human decision inbox; continue only the exact saved direction." }} />}</div>
  </div>;
}
