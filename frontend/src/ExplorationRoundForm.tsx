import { useState } from "react";
import { request, type CreationState } from "./creation.ts";

export function ExplorationRoundForm({ data, selected, selectReferences, saved }: { data: CreationState; selected: string[]; selectReferences: (ids: string[]) => void; saved: () => Promise<void> }) {
  const [title, setTitle] = useState("");
  const [reason, setReason] = useState("");
  const [source, setSource] = useState("");
  const [previous, setPrevious] = useState("");
  const [basedOn, setBasedOn] = useState("");
  const [corrections, setCorrections] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const predecessor = data.rounds.find((item) => item.id === previous);
  const active = data.active_rounds ?? data.rounds;
  const editing = data.rounds.find((item) => item.id === basedOn);
  async function save() {
    setBusy(true); setMessage("");
    try {
      await request("/api/creation/rounds", { title, rationale: reason, source, follows: previous,
        expected_revision: data.revision, references: selected, based_on: basedOn,
        corrections: selected.filter((id) => corrections[id]).map((id) => ({ previous: corrections[id], current: id })),
      });
      await saved(); setTitle(""); setReason(""); setSource(""); setCorrections({}); setPrevious(""); setBasedOn("");
      setMessage("Exploration round saved. Correction intent is recorded; no result was approved or replaced.");
    } catch (error) { setMessage(String(error)); } finally { setBusy(false); }
  }
  return <details className="creation-round-form"><summary>Record an exploration round or corrective pass</summary>
    <p className="prep-help">Uses the {selected.length} references currently selected below. Record why this pass exists and what it revises. This is not approval and does not declare images sent to a generator.</p>
    <label>Round operation<select value={basedOn} onChange={(event) => {
      const round = active.find((item) => item.id === event.target.value);
      setBasedOn(event.target.value);
      if (!round) { setTitle(""); setReason(""); setSource(""); setPrevious(""); setCorrections({}); return; }
      setTitle(round.title); setReason(round.rationale); setSource(round.source);
      const prior = data.rounds.find((item) => item.id === round.follows);
      setPrevious(prior ? active.find((item) => (item.round_id ?? item.id) === (prior.round_id ?? prior.id))?.id ?? round.follows : "");
      setCorrections(Object.fromEntries(round.corrections.map((pair) => [pair.current, pair.previous])));
      selectReferences(round.references.map((item) => item.id));
    }}><option value="">Create a new round</option>{active.map((round) => <option key={round.id} value={round.id}>Revise: {round.title}</option>)}</select></label>
    <label>Round title<input value={title} maxLength={240} onChange={(event) => setTitle(event.target.value)} /></label>
    <label>Purpose / problem being addressed<input value={reason} maxLength={4000} onChange={(event) => setReason(event.target.value)} /></label>
    <label>Source of this observation or decision<input value={source} maxLength={2000} onChange={(event) => setSource(event.target.value)} /></label>
    <label>Earlier round (if this is a follow-up)<select value={previous} onChange={(event) => { setPrevious(event.target.value); setCorrections({}); }}>
      <option value="">Independent round</option>{active.filter((item) => !editing || (item.round_id ?? item.id) !== (editing.round_id ?? editing.id)).map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
    {predecessor && selected.map((id) => <label key={id}>Corrective relation for {data.references.find((item) => item.id === id)?.title ?? id}
      <select value={corrections[id] ?? ""} onChange={(event) => setCorrections((items) => ({ ...items, [id]: event.target.value }))}>
        <option value="">No specific prior artifact being corrected</option>{predecessor.references.filter((item) => item.id !== id).map((ref) => <option key={ref.id} value={ref.id}>Corrects: {ref.title || ref.id}</option>)}
      </select></label>)}
    <button disabled={busy || !selected.length || !title.trim() || !reason.trim() || !source.trim()} onClick={() => void save()}>Save exploration round</button>
    {message && <p role="status">{message}</p>}
  </details>;
}
