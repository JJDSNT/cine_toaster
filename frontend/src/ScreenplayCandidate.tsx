import { useEffect, useMemo, useState } from "react";
import { ContextAssistant } from "./ContextAssistant.tsx";
import { conceptOf, request, type CreationState } from "./creation.ts";

export function ScreenplayCandidate({ id }: { id: string }) {
  const [data, setData] = useState<CreationState | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    request<CreationState>("/api/creation", undefined, controller.signal).then(setData)
      .catch((reason: Error) => { if (!controller.signal.aborted) setError(reason.message); });
    return () => controller.abort();
  }, []);
  const draft = data?.drafts.find((item) => item.id === id && item.kind === "screenplay");
  const concept = draft ? data?.drafts.find((item) => item.id === conceptOf(draft)) : undefined;
  const seen = useMemo(() => ({ room: "screenplay candidate", scene: "", focus: id, selected: id,
    details: JSON.stringify({ saved_version: id, inputs: draft?.inputs ?? [], text: draft?.text.slice(0, 12000),
      canonical: false, storyboard: "not linked to this candidate", approvals: "none implied" }),
  }), [id, draft]);
  return <div className="prep-shell"><header className="prep-header"><div>
    <span className="prep-eyebrow">CINE TOASTER · SCREENPLAY CANDIDATE</span><h1>{draft?.title ?? "Screenplay candidate"}</h1>
    <p>{data?.title ?? "Opening production…"} · {id}</p></div></header>
    <nav className="prep-workspaces" aria-label="Workspaces"><a href="/app/creation.html">Creation / Inception</a>
      <span aria-current="page">Screenplay & Storyboard · candidate</span><a href="/app/preproduction.html">Current film screenplay & shots →</a></nav>
    <div className="prep-body"><main className="prep-work">
      <p className="prep-notice">This is a saved candidate, not the film's current screenplay. Its text has not replaced the screenplay, changed scene coverage or approved any storyboard.</p>
      {error && <p role="alert">{error}</p>}{!data && !error && <p role="status">Loading candidate…</p>}
      {data && !draft && <p role="alert">No screenplay candidate with that id in this production.</p>}
      {draft && <><div className="prep-links"><a href={`/app/creation.html?draft=${encodeURIComponent(draft.id)}`}>Revise as a new version ↗</a>
        {concept && <a href={`/app/creation.html?draft=${encodeURIComponent(concept.id)}`}>Input concept: {concept.title} · {concept.id.slice(-8)} ↗</a>}</div>
        {data?.findings.filter((item) => item.draft === draft.id).map((item, index) => <p className="prep-notice" role="alert" key={index}>{item.input}: {item.message}</p>)}
        <section className="prep-columns" style={{ marginTop: "1.5rem" }}><article className="prep-script"><h2>Screenplay candidate</h2><pre>{draft.text}</pre></article>
          <aside className="prep-board"><h2>Recorded inputs</h2><p className="prep-help">The exact saved concept and reference versions used as declared direction for this candidate.</p>
            {draft.inputs.map((item) => <details key={`${item.kind}:${item.id}`}><summary>{item.kind} · {item.title ?? item.id}</summary><pre>{JSON.stringify(item, null, 2)}</pre></details>)}
            <h2>Storyboard</h2><p>No shot breakdown or visual storyboard is linked to this candidate. Existing film shots are not evidence of coverage for this text.</p>
            <p className="prep-help">Promotion to the current screenplay and candidate-specific shot coverage require separate, explicit operations and are not implemented here.</p></aside></section></>}
    </main><ContextAssistant seen={seen} /></div></div>;
}
