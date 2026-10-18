import { referenceGroups, type CreationState } from "./creation.ts";
import { mediaAddress } from "./preproduction.ts";

export function ReferenceGallery({ data, selected, compare, select, toggleCompare }: {
  data: CreationState; selected: string[]; compare: string[]; select?: (id: string) => void; toggleCompare: (id: string) => void;
}) {
  const anchors = new Set<string>();
  const uses = data.storyboard_uses ?? {};
  return <div className="creation-round-gallery">{referenceGroups(data).map((group) => {
    const body = <>
    {group.round && <details className="creation-round-description"><summary>Round details</summary><p>{group.round.rationale}</p>
      <p>Source: {group.round.source}</p><p>Version {group.round.version ?? 1} · earlier versions retained</p></details>}
    {group.missing.length > 0 && <p className="prep-notice">Missing reference records: {group.missing.join(", ")}. The saved group was retained.</p>}
    <div className="creation-gallery">{group.references.map((item) => {
      const node = data.reference_history.nodes.find((value) => value.id === item.id)!;
      const anchor = anchors.has(item.id) ? undefined : `reference-${encodeURIComponent(item.id)}`;
      anchors.add(item.id);
      return <article key={item.id} id={anchor}>
        {item.images[0] && <a href={mediaAddress(item.images[0])} target="_blank" rel="noreferrer"><img loading="lazy" src={mediaAddress(item.images[0])} alt={item.title} /></a>}
        <h4 title={item.title}>{uses[item.id]?.length ? `${uses[item.id][0].scene} ${uses[item.id][0].shot}` +
          (uses[item.id][0].version ? ` · v${uses[item.id][0].version}` : "") + " — " : ""}{item.title}</h4>
        <div className="creation-card-actions">{select && <label className="creation-check"><input type="checkbox" checked={selected.includes(item.id)} onChange={() => select(item.id)} />Use as input</label>}
          <button aria-pressed={compare.includes(item.id)} onClick={() => toggleCompare(item.id)}>Compare</button></div>
        <details><summary>Details & history</summary><p>{item.title}</p>
          <p>{Array.isArray(item.notes) ? item.notes.join(" · ") : item.notes || "No purpose note recorded."}</p><p>{item.prompt || "No generation prompt recorded."}</p>
          {node.corrects.map((revision) => <p key={revision.id}>Corrective pass for <a href={`#reference-${encodeURIComponent(revision.id)}`}>the earlier study</a>. {revision.reason}</p>)}
          {node.revised_by.map((revision) => <p key={revision.id}>Earlier pass · <a href={`#reference-${encodeURIComponent(revision.id)}`}>Corrective follow-up →</a></p>)}
          <p>{node.uses.length ? `${node.uses.length} recorded downstream uses` : "No generation/draft use recorded"} · Approval not recorded</p>
          {node.selections.map((selection, index) => <p key={index}>{selection.id}: {selection.role} · {selection.purpose}</p>)}
          <small>{item.id} · Image parents: {item.from?.join(", ") || "none recorded"}</small>
          {node.sources.map((source) => <p key={`${source.kind}:${source.id}`}>Text input · {source.kind}: {source.id}</p>)}
          {node.uses.map((use, index) => <p key={index}>{use.evidence === "provider_input" ? "Recorded execution input for" : "Declared input/lineage for"}: {use.kind === "reference"
            ? <a href={`#reference-${encodeURIComponent(use.id)}`}>{use.title}</a>
            : use.kind === "storyboard" ? <a href={`/app/preproduction.html?scene=${encodeURIComponent(use.scene!)}&shot=${encodeURIComponent(use.shot!)}&candidate=${encodeURIComponent(use.id)}`}>{use.title}</a>
            : <a href={`/app/creation.html?draft=${encodeURIComponent(use.id)}`}>{use.title}</a>}</p>)}
          {item.director_on_the_prompt && <><h4>Director observations</h4>{item.director_on_the_prompt.map((note, index) => <p key={index}>{note}</p>)}</>}
          {item.images.slice(1).map((image) => <a key={image} href={mediaAddress(image)} target="_blank" rel="noreferrer"><img loading="lazy" src={mediaAddress(image)} alt={`${item.title} additional image`} /></a>)}
          {item.findings.map((finding, index) => <p className="prep-notice" key={index}>{finding.severity}: {finding.message}</p>)}
        </details>
      </article>;
    })}</div></>;
    // Storyboard drawings are the storyboard's: filed apart and folded, so Inception stays Inception.
    if (group.storyboard) return <details className="creation-image-round" key={group.id}>
      <summary><strong>{group.title}</strong> · {group.references.length} images, by scene and shot ·{" "}
        <a href="/app/preproduction.html">open them in Screenplay & Storyboard</a></summary>{body}</details>;
    return <section className="creation-image-round" key={group.id} aria-label={group.number ? `Round ${group.number}: ${group.title}` : group.title}>
      <div className="prep-section-heading"><h3>{group.number ? `Round ${group.number} · ` : ""}{group.title}</h3>
        <span className="prep-help">{group.references.length} images</span></div>{body}</section>;
  })}</div>;
}
