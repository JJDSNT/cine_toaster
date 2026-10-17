import { useEffect, useMemo, useState } from "react";
import { ContextAssistant } from "./ContextAssistant.tsx";
import { ReferenceEvolution } from "./ReferenceEvolution.tsx";
import { ReferenceGallery } from "./ReferenceGallery.tsx";
import { InceptionReview } from "./InceptionReview.tsx";
import { DecisionLink } from "./DecisionInbox.tsx";
import { ArtDirection } from "./ArtDirection.tsx";
import { ProductionProgress } from "./ProductionProgress.tsx";
import { candidateAddress, request, type CreationState, type Draft } from "./creation.ts";

/** One line for a batch of pictures: the progress strip above says where it leads. */
function jobSummary(jobs: { state: string }[]): string {
  const count = (state: string) => jobs.filter((job) => job.state === state).length;
  const parts = [["kept", count("adopted")], ["ready", count("succeeded")], ["drawing", count("running")],
                 ["queued", count("queued")], ["refused", count("failed")]].filter(([, n]) => n) as [string, number][];
  return `${jobs.length} picture job(s): ${parts.map(([label, n]) => `${n} ${label}`).join(", ")} · details`;
}

interface Job { id: string; kind: string; state: string; message?: string; error?: unknown; adopted_at?: string; result?: { summary?: { title?: string } } }

export function Creation() {
  const [data, setData] = useState<CreationState | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [focused, setFocused] = useState(() => new URLSearchParams(window.location.search).get("draft") ?? "");
  const [compare, setCompare] = useState<string[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobsError, setJobsError] = useState("");
  const [busy, setBusy] = useState(false);
  const [continuation, setContinuation] = useState<{ decisionId: string; attempt?: string } | null>(null);
  async function reload() { setData(await request<CreationState>("/api/creation")); }
  async function act(action: () => Promise<void>) {
    setBusy(true); setError("");
    try { await action(); } catch (reason) { setError(String(reason)); } finally { setBusy(false); }
  }
  function open(draft: Draft) {
    setFocused(draft.id);
    window.history.pushState(null, "", `?draft=${encodeURIComponent(draft.id)}`);
  }
  useEffect(() => {
    const controller = new AbortController();
    request<CreationState>("/api/creation", undefined, controller.signal).then(setData)
      .catch((reason: Error) => { if (!controller.signal.aborted) setError(reason.message); });
    const back = () => setFocused(new URLSearchParams(window.location.search).get("draft") ?? "");
    window.addEventListener("popstate", back);
    return () => { controller.abort(); window.removeEventListener("popstate", back); };
  }, []);
  useEffect(() => {
    if (data && window.location.hash.startsWith("#reference-"))
      document.getElementById(window.location.hash.slice(1))?.scrollIntoView({ block: "center" });
  }, [data]);
  useEffect(() => {
    let active = true;
    async function refreshJobs() {
      try {
        const result = await request<Job[]>("/api/jobs");
        if (active) { setJobs(result.filter((item) => item.kind === "generate_reference").map((item) => item.adopted_at ? { ...item, state: "adopted" } : item)); setJobsError(""); }
      } catch (reason) { if (active) setJobsError(String(reason)); }
    }
    void refreshJobs();
    const timer = window.setInterval(() => { void refreshJobs(); }, 2500);
    return () => { active = false; window.clearInterval(timer); };
  }, []);
  const current = data?.drafts.find((item) => item.id === focused);
  const inputs = current?.inputs.filter((item) => item.kind === "reference").map((item) => item.id) ?? [];
  const storyboardUses = data?.reference_history.nodes.flatMap((node) => node.uses.filter((item) => item.kind === "storyboard")) ?? [];
  const usedShots = new Set(storyboardUses.map((item) => `${item.scene}/${item.shot}`)).size;
  const firstUse = storyboardUses[0];
  const storyboardAddress = firstUse
    ? `/app/preproduction.html?scene=${encodeURIComponent(firstUse.scene!)}&shot=${encodeURIComponent(firstUse.shot!)}`
    : "/app/preproduction.html";
  const seen = useMemo(() => ({ room: "creation", scene: "", focus: focused, selected: inputs.join(","),
    details: JSON.stringify({ saved_version: current?.id ?? null, reference_inputs: inputs, compared_references: compare,
      role: "Human situational view: discuss with the copilot, inspect results and decide at explicit gates. No manual authoring forms.",
      inception_assessment: data?.inception_review?.current ? {
        id: data.inception_review.current.id, status: data.inception_review.current.status,
        summary: data.inception_review.current.summary, readiness: data.inception_review.current.readiness,
        proposal: data.inception_review.current.proposal, decision: data.inception_review.current.decision,
      } : null,
      purpose: "The agent works through application operations. Drafts and reuse are not human approvals." }),
  }), [current, focused, inputs.join(","), compare.join(","), data?.inception_review]);
  return <div className="prep-shell">
    <header className="prep-header"><div><span className="prep-eyebrow">CINE TOASTER · FROM IDEA TO FILM</span>
      <h1>{data?.title ?? "Creation / Inception"}</h1><p>Discuss with the copilot. Inspect the work. Direct the next pass.</p></div>
      <button disabled={busy} onClick={() => void act(async () => { await reload(); setNotice("Production records refreshed."); })}>Refresh records</button></header>
    <nav className="prep-workspaces" aria-label="Workspaces"><DecisionLink /><span aria-current="page">Creation / Inception</span>
      <a href={storyboardAddress}>Screenplay & Storyboard →</a><a href="/?view=scenes">Production →</a>
      <a href="/?view=sequences">Assembly & versions</a><a href="/">Control Room</a></nav>
    <ProductionProgress />
    {error && <p className="prep-notice" role="alert">{error}</p>}
    {notice && <p className="creation-notice" role="status">{notice}</p>}
    <div className="prep-body creation-body">
      <aside className="prep-scenes creation-history" aria-label="Saved candidates"><h2>Concepts & drafts</h2>
        {!data && <p role="status">{error ? "Records unavailable" : "Loading records…"}</p>}
        {data && !data.drafts.length && <p>No separate concept drafts recorded. The existing visual explorations are shown by round.</p>}
        {data?.drafts.slice().reverse().map((item) => <button key={item.id} aria-current={item.id === focused ? "true" : undefined}
          onClick={() => open(item)}><small>{item.kind} · {item.created_at.slice(0, 16)}</small>
          <strong>{item.title}</strong><span>{item.inputs.length} inputs · retained version</span></button>)}
      </aside>
      <main className="prep-work creation-work">
        <section className="prep-status"><div><strong>Creation / Inception</strong>
          <p>The copilot develops ideas and produces alternatives. This workspace shows results, their history and known downstream use. Human approvals remain explicit production decisions.</p>
          {usedShots > 0 && <a href={storyboardAddress}>View storyboard drawings · {usedShots} shots →</a>}</div>
          <span className="prep-badge">Exploration and reuse do not imply approval</span></section>
        {data?.findings.map((item, index) => <p className="prep-notice" role="alert" key={index}>{item.draft} · {item.input}: {item.message}</p>)}
        {data && <InceptionReview key={data.inception_review?.current?.id ?? "none"} data={data} reload={reload}
          onDecision={(decisionId, attempt) => setContinuation({ decisionId, attempt })} />}
        {data && <ArtDirection data={data} />}
        {focused && !current && data && <p role="alert">That saved candidate is not in this production.</p>}
        {current && <section className="creation-editor" aria-label="Saved candidate">
          <h2>{current.title}</h2><p className="prep-help">{current.kind} · retained candidate, not an approved production decision</p>
          <pre>{current.text}</pre>
          {current.kind === "screenplay" && <a href={candidateAddress(current.id)}>Review screenplay candidate →</a>}
          <details><summary>Recorded inputs & lineage</summary><p>Based on: {current.based_on || "First candidate"}</p><pre>{JSON.stringify(current.inputs, null, 2)}</pre></details>
        </section>}
        <section className="creation-references" aria-label="Reference exploration"><div className="prep-section-heading"><h2>Visual references & alternatives</h2><span>{data?.references.length ?? 0} reference records · all retained</span></div>
          <p className="prep-help">Compare results and discuss the next direction with the copilot. Each round preserves its earlier alternatives.</p>
          {compare.length > 0 && <div className="creation-compare" aria-label="Reference comparison">{compare.map((id) => {
            const item = data?.references.find((ref) => ref.id === id);
            return item ? <figure key={id}><figcaption>{item.title}</figcaption>{item.images[0] && <img src={`/media/${item.images[0].split("/").map(encodeURIComponent).join("/")}`} alt={`${item.title} comparison`} />}</figure> : null;
          })}</div>}
          {data && <ReferenceGallery data={data} selected={inputs} compare={compare}
            toggleCompare={(id) => setCompare((ids) => ids.includes(id) ? ids.filter((item) => item !== id) : [...ids.slice(-1), id])} />}
          {data && <details className="creation-history-detail"><summary>History, revisions & downstream use</summary><ReferenceEvolution data={data} /></details>}
        </section>
        {jobsError && <p role="alert">Reference jobs could not be refreshed: {jobsError}</p>}
        {jobs.length > 0 && <details className="creation-jobs"><summary>{jobSummary(jobs)}</summary>
        {jobs.map((job) => <article className="creation-job" key={job.id}><h3>{job.result?.summary?.title ?? "Reference exploration"} · {job.state}</h3>
          {job.message && <p>{job.message}</p>}{Boolean(job.error) && <pre role="alert">{JSON.stringify(job.error)}</pre>}
          {job.state === "succeeded" && <><img src={`/api/creation/reference-preview?job=${encodeURIComponent(job.id)}`} alt="Generated reference awaiting review" />
            <button disabled={busy} onClick={() => void act(async () => {
              await request(`/api/jobs/${encodeURIComponent(job.id)}/adopt`, { overwrite: false }); await reload();
              setJobs((items) => items.map((item) => item.id === job.id ? { ...item, state: "adopted" } : item));
              setNotice("Reference retained. Earlier images were preserved. This is not a storyboard or master approval.");
            })}>Keep as a new reference</button></>}
          {["queued", "running"].includes(job.state) && <button disabled={busy} onClick={() => void act(async () => {
            const next = await request<Job>(`/api/jobs/${encodeURIComponent(job.id)}/cancel`, {});
            setJobs((items) => items.map((item) => item.id === next.id ? next : item));
          })}>Cancel generation</button>}
          {job.state === "adopted" && <p>Retained as a new reference; earlier images were preserved.</p>}
        </article>)}</details>}
      </main>
      <ContextAssistant seen={seen} continuation={continuation} onRecordsChanged={() => { void reload().catch((reason) => setError(String(reason))); }} />
    </div>
  </div>;
}
