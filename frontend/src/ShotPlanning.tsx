import type { CreationState, ContinuityReview } from "./creation.ts";

function Report({ report }: { report: ContinuityReview }) {
  return <article className="prep-plan-review">
    <h3>Continuity · {report.stale ? "Sources changed / superseded" : report.verdict.replaceAll("_", " ")}</h3>
    <p>{report.summary}</p>
    <p className="prep-help">{report.plan ? `Proposal ${report.plan}` : `Canonical audit · ${report.scene || "whole film"}`} · advisory, not human approval</p>
    {report.findings.map((finding, index) => <div key={index}>
      <strong>{finding.basis} · {finding.severity}</strong><p>{finding.evidence}</p><p>{finding.correction}</p>
      <small>Sources: {finding.sources.join(", ") || "Not established"}</small>
    </div>)}
    {report.checks.length > 0 && <details><summary>Computed scope checks · {report.checks.length}</summary>
      {report.checks.map((check, index) => <p key={index}>{check.severity} · {check.evidence || check.message || check.code}</p>)}
    </details>}
    {report.plan && report.canonical_checks.length > 0 && <details><summary>Separate canonical findings · {report.canonical_checks.length}</summary>
      {report.canonical_checks.map((check, index) => <p key={index}>{check.severity} · {check.evidence || check.message || check.code}</p>)}
    </details>}
    <ul>{report.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul>
  </article>;
}

export function ShotPlanning({ data, scene }: { data: CreationState; scene: string }) {
  const plans = (data.directing?.plans ?? []).filter((item) => item.scene === scene);
  const reports = (data.directing?.reviews ?? []).filter((item) => !item.scene || item.scene === scene);
  return <section className="prep-planning" aria-label="Directing and continuity">
    <h2>Directing & continuity</h2>
    <p className="prep-help">Agent work from the linked screenplay. Proposals are retained separately from canonical shots and storyboard images.</p>
    {!plans.length && <p>No shot-planning proposal saved for this scene. Ask the assistant to develop its decoupage or inspect continuity.</p>}
    {[...plans].reverse().map((plan, index) => <details key={plan.id} open={index === 0} className="prep-plan">
      <summary>{plan.title} · {plan.shots.length} shots · {plan.stale ? "Sources changed" : "Proposal, not canonical"}</summary>
      <p>{plan.intention}</p><p className="prep-help">{plan.id}{plan.based_on ? ` · revision of ${plan.based_on}` : " · first proposal"}</p>
      <ol>{plan.shots.map((shot) => <li key={shot.id}>
        <h3>{shot.id} · {shot.label} · {shot.duration_seconds}s</h3><p>{shot.action}</p>
        <p>{shot.framing} · {shot.camera_intent}</p>
        <p className="prep-help">Screenplay units: {shot.script_units.join(", ")}{shot.existing_shot ? ` · canonical association: ${shot.existing_shot}` : ""}</p>
        {shot.transition_intent && <p>Transition intent: {shot.transition_intent}</p>}
        {(shot.state_in.length > 0 || shot.state_out.length > 0) && <details><summary>Proposed entry / exit facts · not measured</summary>
          <p>Entry: {shot.state_in.map((fact) => `${fact.subject} ${fact.attribute}: ${fact.value}`).join("; ") || "Not specified"}</p>
          <p>Exit: {shot.state_out.map((fact) => `${fact.subject} ${fact.attribute}: ${fact.value}`).join("; ") || "Not specified"}</p>
        </details>}
      </li>)}</ol>
      {plan.checks.map((check, n) => <p key={n} role="status">{check.severity} · {check.evidence}</p>)}
      {reports.filter((report) => report.plan === plan.id).map((report) => <Report key={report.id} report={report} />)}
    </details>)}
    {reports.filter((report) => !report.plan).map((report) => <Report key={report.id} report={report} />)}
  </section>;
}
