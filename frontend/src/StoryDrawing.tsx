import { mediaAddress } from "./preproduction.ts";
import { drawingPreview, type StoryDrawing as Drawing } from "./storyboard.ts";

export function StoryDrawing({ versions, candidate, choose }: {
  versions: Drawing[]; candidate: string; choose: (id: string) => void;
}) {
  const drawing = drawingPreview(versions, candidate);
  if (!drawing) return <div className="prep-empty"><strong>{candidate ? "Requested drawing version not found for this shot" : "No storyboard drawing for this shot"}</strong>
    <p>Concept references and 3D studies remain separate. A final face choice is not required to explore this shot.</p>
    {candidate && <button onClick={() => choose("")}>Return to latest preview</button>}</div>;
  return <div className="prep-drawing">
    {drawing.image_available ? <figure><img src={mediaAddress(drawing.image.path)} alt={`${drawing.shot} storyboard draft`} />
      <figcaption>Storyboard draft · v{drawing.version} · Approval not recorded · Preview, not a selected master</figcaption></figure>
      : <p className="prep-notice" role="alert">Recorded drawing image is unavailable. Its history has been retained.</p>}
    <p>{drawing.note || drawing.title}</p>
    {drawing.findings.map((item, index) => <p key={index} className="prep-notice">{item.message}</p>)}
    <p className="prep-help">Inception inputs: {drawing.inputs.length ? drawing.inputs.map((item, index) => <span key={item.id}>
      {index > 0 && " · "}<a href={`/app/creation.html#reference-${encodeURIComponent(item.id)}`}>{item.title || item.id}</a>
    </span>) : "No reference inputs recorded"}</p>
    <details><summary>Versions & origin · {versions.length} retained</summary>
      <p>The latest version is the default preview, not an approval. Declared references and actual generation inputs are recorded separately.</p>
      {versions.map((item) => <button key={item.id} aria-pressed={item.id === drawing.id} onClick={() => choose(item.id)}>v{item.version} · {item.title}</button>)}
      <pre>{JSON.stringify({ id: drawing.id, based_on: drawing.based_on, inputs: drawing.inputs, provenance: drawing.provenance }, null, 2)}</pre>
    </details>
  </div>;
}
