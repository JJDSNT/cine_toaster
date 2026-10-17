import type { CreationState } from "./creation.ts";

const evidence = (value: string) => value === "provider_input" ? "Recorded image input"
  : value === "provider_input_changed" ? "Recorded image input · hash differs" : "Declared lineage";
export function ReferenceEvolution({ data }: { data: CreationState }) {
  const history = data.reference_history;
  const rounds = data.active_rounds ?? data.rounds;
  const titleOf = (id: string) => data.references.find((item) => item.id === id)?.title || id;
  const jump = (id: string) => `#reference-${encodeURIComponent(id)}`;
  return <section className="creation-evolution" aria-label="Reference evolution">
    <h3>Evolution, corrections & downstream use</h3>
    <div className="creation-metrics"><span>{history.summary.reused} reused downstream</span>
      <span>{history.summary.provider_input_links} recorded image-input links</span>
      <span>{history.summary.cast_selections} cast designations</span><span>{rounds.length} recorded exploration rounds</span></div>
    <p className="prep-help">An image can be reused while still needing review. A corrective pass is not automatically approved; an image parent is not necessarily its previous creative version.</p>
    {rounds.length ? <div className="creation-rounds">{rounds.map((round, index) => <article key={round.id} id={round.id}>
      <span className="prep-eyebrow">EXPLORATION ROUND {index + 1}{round.follows ? " · FOLLOW-UP" : ""}</span>
      <h3>{round.title}</h3><p>{round.rationale}</p>
      <p className="prep-help">Recorded source: {round.source}</p>
      <div className="prep-links">{round.references.map((ref) => <a key={ref.id} href={jump(ref.id)}>{titleOf(ref.id)}</a>)}</div>
      {round.corrections.map((pair) => <p className="creation-correction" key={`${pair.previous}:${pair.current}`}>
        <a href={jump(pair.previous)}>{titleOf(pair.previous)}</a><span> → corrective pass → </span><a href={jump(pair.current)}>{titleOf(pair.current)}</a></p>)}
      <p className="prep-badge">{round.corrections.length ? "Correction intent recorded · result approval not recorded" : "Exploration recorded · not an approval"}</p>
    </article>)}</div> : <p className="prep-notice">No exploration-round decisions recorded yet. Image lineage below is known; it does not establish which pass revised or replaced another.</p>}
    <details open><summary>Image lineage & known uses</summary><ol className="creation-lineage">{history.nodes.map((node) => <li key={node.id} style={{ marginLeft: `${Math.min(node.depth, 4) * 1.2}rem` }}>
      <a href={jump(node.id)}>{node.title}</a>
      <div className="creation-lineage-facts">{node.parents.length ? node.parents.map((parent) => <span key={parent.id}>{evidence(parent.evidence)}: <a href={jump(parent.id)}>{titleOf(parent.id)}</a></span>)
        : <span>{node.sources.length ? "Text-guided exploration · no recorded image parent" : "Source reference · no recorded image parent"}</span>}
        {node.uses.length > 0 && <span className="creation-used">Used downstream: {node.uses.length}{node.uses.some((item) => item.evidence === "provider_input") ? " · includes recorded generation input" : " · declared direction/lineage"}</span>}
        {node.revised_by.length > 0 && <span className="creation-revised">Earlier pass · {node.revised_by.length} corrective follow-up</span>}
        {node.corrects.length > 0 && <span className="creation-revised">Corrective pass · review outcome not recorded</span>}
      </div></li>)}</ol></details>
    <p className="prep-help">{history.summary.review}</p>
  </section>;
}
