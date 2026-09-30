// Editing a cut from the canvas (plan step 13). The canvas never writes the
// film: it sends the same command the other interfaces send (`set_cut`,
// `clear_cut`), against the revision it was drawn from, so an edit made on a
// stale view is refused rather than applied over someone else's.
import { useEffect, useState } from "react";
import { CUT_NAMES } from "./edges.tsx";
import type { CutData } from "./types.ts";

interface Transition { id: string; name?: string; label?: string }

let catalog: Promise<Transition[]> | null = null;
function transitions(): Promise<Transition[]> {
  catalog ??= fetch("/api/transitions").then((response) => (response.ok ? response.json() : []));
  return catalog;
}

async function command(name: string, payload: Record<string, unknown>): Promise<void> {
  const response = await fetch("/api/commands", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command: name, actor: { id: "canvas", kind: "human" }, ...payload }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body?.error?.message ?? `The runtime answered ${response.status}`);
  }
}

export function CutEditor({ scene, shot, data, onSaved }: { scene: string; shot: string; data: CutData; onSaved: () => void }) {
  const [type, setType] = useState(data.cut || "hard");
  const [chain, setChain] = useState(data.chain === "frame");
  const [reason, setReason] = useState(data.reason || "");
  const [transition, setTransition] = useState(data.transition || "");
  const [ms, setMs] = useState(data.transition_ms || 0);
  const [why, setWhy] = useState(data.transition_reason || "");
  const [options, setOptions] = useState<Transition[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { transitions().then(setOptions).catch(() => setOptions([])); }, []);

  const run = async (name: string, payload: Record<string, unknown>) => {
    setBusy(true);
    setError("");
    try {
      await command(name, { scene_id: scene, shot_id: shot, expected_revision: data.revision, ...payload });
      onSaved();
    } catch (reasonText) {
      setError((reasonText as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const save = () => run("set_cut", {
    cut: {
      type, chain: chain ? "frame" : "", reason,
      transition: transition ? { id: transition, duration_ms: ms || null, reason: why } : null,
    },
  });

  return (
    <form className="cut-editor" onSubmit={(event) => { event.preventDefault(); save(); }}>
      <label>Cut
        <select value={type} onChange={(event) => setType(event.target.value)}>
          {Object.entries(CUT_NAMES).map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </select>
      </label>
      <label className="inline"><input type="checkbox" checked={chain} onChange={(event) => setChain(event.target.checked)} /> Opens on the previous last frame</label>
      <label>Why
        <input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="What the cut does" />
      </label>
      <label>Transition
        <select value={transition} onChange={(event) => setTransition(event.target.value)}>
          <option value="">None (a straight join)</option>
          {options.map((item) => <option key={item.id} value={item.id}>{item.name || item.label || item.id}</option>)}
        </select>
      </label>
      {transition && (
        <>
          <label>Duration (ms)<input type="number" min={0} step={40} value={ms} onChange={(event) => setMs(Number(event.target.value))} /></label>
          <label>Why this transition<input value={why} onChange={(event) => setWhy(event.target.value)} placeholder="A choice without a reason cannot be reviewed" /></label>
        </>
      )}
      {data.decided && <p className="hint">Decided here; the breakdown says {CUT_NAMES[data.authored] || data.authored}.</p>}
      {error && <p className="finding error">{error}</p>}
      <div className="actions">
        <button type="submit" disabled={busy}>Save the cut</button>
        {data.decided && <button type="button" disabled={busy} onClick={() => run("clear_cut", {})}>Back to the breakdown</button>}
      </div>
    </form>
  );
}

/** Start a block's workflow, or a single shot's ({shot: …}). */
export async function startWorkflow(scene: string, target: { block?: string; shot?: string }, revision: number): Promise<void> {
  await command("start_workflow", { scene_id: scene, ...target, expected_revision: revision });
}
