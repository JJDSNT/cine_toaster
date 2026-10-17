import type { CreationState } from "./creation.ts";

const verdicts = { ready_for_human: "Ready for human creative review", needs_changes: "Corrections needed", inconclusive: "Visual evidence inconclusive" };

export function ArtDirection({ data }: { data: CreationState }) {
  const art = data.art_direction;
  if (!art?.briefs.length) return null;
  return <section className="creation-editor" aria-label="Art direction and visual prevalidation">
    <h2>Art direction & visual prevalidation</h2>
    <p className="prep-help">Agent work and advisory image checks — never a human approval. All versions remain available.</p>
    {art.briefs.slice().reverse().map((brief, index) => <details key={brief.id} open={index === 0}>
      <summary>{brief.title} · retained brief</summary><pre>{brief.text}</pre>
      <ul>{brief.criteria.map((criterion) => <li key={criterion}>{criterion}</li>)}</ul>
      {art.reviews.filter((review) => review.brief === brief.id).slice().reverse().map((review) => <article key={review.id}>
        <h3>{review.stale ? "Material changed — reassessment needed" : verdicts[review.verdict]}</h3>
        <p>{review.summary}</p>
        <p className="prep-help">{review.images.length} inspected images · not a creative approval</p>
        {review.findings.map((finding) => <div key={finding.criterion}>
          <strong>{finding.criterion} · {finding.status}</strong><p>{finding.evidence}</p><p>{finding.correction}</p>
        </div>)}
        <details><summary>Exact inspected versions</summary><pre>{JSON.stringify(review.images, null, 2)}</pre></details>
      </article>)}
    </details>)}
  </section>;
}
