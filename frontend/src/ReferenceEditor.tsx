// Editing what a shot's picture is made from, from the canvas (CT-0046). Like a
// cut, it is a decision over the breakdown: the canvas sends `set_reference`
// or `clear_reference` against the revision it was drawn from, and the
// breakdown is not rewritten.
import { useState } from "react";
import { command } from "./CutEditor.tsx";
import type { ShotData } from "./types.ts";

interface Props {
  shot: ShotData;
  /** The other shots of the scene, as possible sources. */
  shots: ShotData[];
  cast: { id: string; label: string }[];
  /** The scene's location plates: the empty set, by camera. */
  plates: { camera: string; path: string }[];
  revision: number;
  onSaved: () => void;
}

export function ReferenceEditor({ shot, shots, cast, plates, revision, onSaved }: Props) {
  const [from, setFrom] = useState(shot.from[0] ?? "");
  const [faces, setFaces] = useState<string[]>(shot.with);
  const [why, setWhy] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const known = shots.some((item) => item.number === from) || plates.some((item) => `location:${item.camera}` === from) || !from;

  const run = async (name: string, payload: Record<string, unknown>) => {
    setBusy(true);
    setError("");
    try {
      await command(name, { scene_id: shot.scene, shot_id: shot.shot, expected_revision: revision, rationale: why, ...payload });
      onSaved();
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const save = () => run("set_reference", { from, ...(shot.derived ? { with: faces } : {}) });
  const same = (a: string, b: string) => a.toUpperCase() === b.toUpperCase();
  const toggle = (id: string) => setFaces((current) => (current.some((name) => same(name, id))
    ? current.filter((name) => !same(name, id)) : [...current, id]));

  return (
    <form className="cut-editor reference-editor" onSubmit={(event) => { event.preventDefault(); save(); }}>
      <label>Made from
        <select value={known ? from : "__other"} onChange={(event) => setFrom(event.target.value === "__other" ? from : event.target.value)}>
          <option value="">{shot.from.length ? "Keep as it is" : "Choose a shot"}</option>
          {shots.filter((item) => item.shot !== shot.shot).map((item) => (
            <option key={item.shot} value={item.number}>{item.shot} · {item.label.slice(0, 40)}</option>
          ))}
          {plates.length > 0 && (
            <optgroup label="The empty set (location plates)">
              {plates.map((item) => <option key={item.camera} value={`location:${item.camera}`}>Plate from {item.camera}</option>)}
            </optgroup>
          )}
          {!known && <option value="__other">{from}</option>}
        </select>
      </label>
      {shot.derived && (
        <fieldset>
          <legend>Faces from the cast</legend>
          {cast.map((member) => (
            <label key={member.id} className="inline">
              <input type="checkbox" checked={faces.some((name) => same(name, member.id))}
                     onChange={() => toggle(member.id)} /> {member.label}
            </label>
          ))}
        </fieldset>
      )}
      <label>Why
        <input value={why} onChange={(event) => setWhy(event.target.value)} placeholder="Kept with the decision" />
      </label>
      {shot.reference_decided && (
        <p className="hint">Decided here; the breakdown says {shot.authored_from.join(", ") || "nothing"}
          {shot.derived ? `, with ${shot.authored_with.join(", ") || "no faces"}` : ""}.</p>
      )}
      {error && <p className="finding error">{error}</p>}
      <div className="actions">
        <button type="submit" disabled={busy || (!from && !shot.derived)}>Save the reference</button>
        {shot.reference_decided && <button type="button" disabled={busy} onClick={() => run("clear_reference", {})}>Back to the breakdown</button>}
      </div>
    </form>
  );
}
