import { useState } from "react";
import { request, type CreationState } from "./creation.ts";

const statusNames = { ready: "Enough to proceed", needs_work: "Gaps to resolve", not_assessed: "Not assessed" };

export function InceptionReview({ data, reload, onDecision, title = "Is there enough to proceed?" }: {
  data: CreationState; reload: () => Promise<void>; onDecision?: (decisionId: string, attempt?: string) => void; title?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [guidance, setGuidance] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const current = data.inception_review?.current;
  if (!current) return <section className="creation-readiness" aria-label="Inception readiness">
    <h2>{title}</h2><p>No agent assessment recorded yet. A reference count does not establish readiness.</p>
    <p className="prep-help">The agent needs to assess the next steps and present a recommendation; there is no approval request yet.</p>
  </section>;
  async function decide(outcome: "approved" | "changes_requested") {
    setBusy(true); setError("");
    try {
      const result = await request<{ decision: { id: string } }>("/api/creation/direction", { assessment: current!.id, outcome, guidance,
        advance: outcome === "approved" && Boolean(current!.handoff_preview?.can_advance),
        expected_handoff_digest: current!.handoff_preview?.sha256 ?? "",
        expected_revision: data.revision });
      if (result.decision?.id) onDecision?.(result.decision.id);
      await reload(); setEditing(false); setGuidance("");
    } catch (reason) { setError(String(reason)); } finally { setBusy(false); }
  }
  const handoff = data.handoffs?.find((item) => item.decision === current.decision?.id);
  return <section id="direction-review" className="creation-readiness" aria-label="Inception readiness">
    <div className="prep-section-heading"><h2>{title}</h2><span className="prep-badge">
      {current.status === "awaiting_decision" ? "Awaiting your decision" : current.status === "approved" ? "Direction approved"
        : current.status === "changes_requested" ? "Changes requested · agent to reassess" : "Material changed · agent to reassess"}</span></div>
    <p>{current.summary}</p>
    <div className="creation-readiness-destinations">{current.readiness.map((item) => <article key={item.destination}>
      <h3>{item.destination === "screenplay" ? "Screenplay" : item.destination === "storyboard" ? "Storyboard" : "Shot masters"}</h3>
      <strong>{statusNames[item.status]}</strong><p>{item.summary}</p>
      {item.gaps.length > 0 && <details><summary>{item.gaps.length} gap{item.gaps.length === 1 ? "" : "s"} & next actions</summary>
        {item.gaps.map((gap, index) => <div key={index}><p>{gap.description}</p><p className="prep-help">{gap.owner === "agent" ? "Agent" : "Human creative decision"}: {gap.next_action}</p></div>)}
      </details>}
    </article>)}</div>
    <div className="creation-direction"><h3>{current.proposal.question}</h3><p>{current.proposal.why}</p>
      <p className="prep-help">Scope: {current.proposal.scope}</p><p>Next step: {current.proposal.next_step}</p>
      {current.status === "awaiting_decision" && <>
        <p className="prep-help">This approves the proposed direction, not finished storyboard images, cast masters or paid generation.</p>
        {current.handoff_preview?.can_advance && <p>Advance approved inputs to storyboard development: <strong>
          {current.handoff_preview.target?.scene} / {current.handoff_preview.target?.shots.join(", ")}</strong>.
          The assistant will develop this scope; new image generation needs separate quota consent.</p>}
        {!current.handoff_preview?.can_advance && current.proposal.destination === "storyboard" && current.proposal.review_kind !== "storyboard_candidates" &&
          <p className="prep-help">This records direction only. Automatic storyboard development needs an explicit existing scene/shot target;
            promoting local proposed shot IDs into canonical shots is not implemented.</p>}
        <div className="prep-actions"><button disabled={busy} onClick={() => void decide("approved")}>
          {current.handoff_preview?.can_advance ? "Approve & advance" : "Approve direction"}</button>
          <button disabled={busy} aria-expanded={editing} onClick={() => setEditing(!editing)}>Request changes</button></div>
        {editing && <div className="creation-review-guidance"><label htmlFor="inception-guidance">Direction for the next pass</label>
          <textarea id="inception-guidance" value={guidance} maxLength={4000} rows={3} onChange={(event) => setGuidance(event.target.value)} />
          <button disabled={busy || !guidance.trim()} onClick={() => void decide("changes_requested")}>Send direction</button></div>}
      </>}
      {current.material_changed && <p className="prep-notice">The material differs from the assessed version. The agent must update its assessment before a new decision.</p>}
      {current.decision && <p role="status">{current.decision.outcome === "approved" ? "Your direction approval was recorded." : "Your request for changes was recorded."}
        {current.decision.guidance && ` ${current.decision.guidance}`}</p>}
      {current.next_agent_action && <p className="prep-help">Next agent instruction: {current.next_agent_action.instruction}
        {" · This instruction alone is not proof of execution; check the assistant's activity."}</p>}
      {handoff && <div><h3>Approved stage input · {handoff.target.scene}</h3>
        <p>{handoff.stale ? "Source material changed; reassessment needed." :
          `${handoff.outputs.length} retained output(s) · ${handoff.target.shots.length} target shot(s). This is not a running-job claim.`}</p>
        {handoff.outputs.map((item) => <p key={item.id}><a href={item.url}>See storyboard {item.scene} / {item.shot}</a></p>)}
        {!handoff.stale && onDecision && <button onClick={() => onDecision(handoff.decision,
          `retry-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`)}>Continue approved work</button>}
      </div>}
      {error && <p role="alert">{error} · Your direction text was retained. Refresh records before retrying.</p>}
    </div>
    <details><summary>Assessment & decision history · {data.inception_review!.history.length} retained</summary>
      <pre>{JSON.stringify({ assessments: data.inception_review!.history, decisions: data.inception_review!.decisions }, null, 2)}</pre>
    </details>
  </section>;
}
