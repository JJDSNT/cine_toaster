// The sequence as the director reviews it (Demo 01, 2026-10-18): every shot's current drawing in order,
// as a contact sheet, and the storyboard animatic -- the drawings held for their breakdown durations.
import { useEffect, useState } from "react";
import { request } from "./creation.ts";
import "./sequence-storyboard.css";

interface Candidate { path: string; url: string; size?: string; ratio?: number; frame_ok?: boolean }
interface Master { gate: string; state: string; candidates: Candidate[]; chosen: string; rationale: string; decided_by?: string; findings?: string[] }
interface Shot { scene: string; scene_title: string; shot: string; seconds: number; board: string | null; version: number | null; image_url: string; master?: Master | null }

// A person's decision on a master picture: the same application command the control room sends (SPEC-0009).
async function decideGate(scene: string, gate: string, outcome: string, chosen: string, rationale: string) {
  const response = await fetch("/api/commands", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command: "decide_gate", scene_id: scene, gate_id: gate, outcome, chosen, rationale,
      actor: { id: "director-gui", kind: "human" } }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body?.error?.message ?? `The runtime answered ${response.status}`);
  }
}
interface View {
  sequences: { id: string; label: string }[]; sequence: string; shots: Shot[]; seconds: number;
  animatics: { version: number; url: string }[];
  phases?: Record<string, { phase: string; changed_since: boolean; since: string }>;
}

export function SequenceStoryboard({ onOpen }: { onOpen?: (scene: string, shot: string) => void }) {
  const [view, setView] = useState<View | null>(null);
  const [sequence, setSequence] = useState("");
  const [shown, setShown] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  async function load(chosen = sequence) {
    try {
      const value = await request<View>(`/api/storyboard/sequence?sequence=${encodeURIComponent(chosen)}`);
      setView(value); setSequence(value.sequence); setError("");
    } catch (reason) { setError(String(reason)); }
  }
  useEffect(() => { void load(""); }, []);
  if (!view || !view.sequence) return error ? <p className="prep-notice" role="alert">{error}</p> : null;
  const label = view.sequences.find((item) => item.id === view.sequence)?.label ?? view.sequence;
  const drawn = view.shots.filter((shot) => shot.board).length;
  const phases = Object.entries(view.phases ?? {});
  const approved = phases.filter(([, item]) => item.phase === "production" && !item.changed_since).map(([id]) => id);
  const whole = phases.length > 0 && approved.length === phases.length;
  async function decide(approve: boolean) {
    const why = window.prompt(approve ? `Approve the storyboard of ${label} as what will be produced. Why? (optional)`
      : `Reopen the storyboard of ${label}. Why?`);
    if (why === null) return;
    setBusy(true); setError("");
    try {
      const done = await request<{ decided: string[]; skipped: string[] }>("/api/storyboard/sequence-decision",
        { sequence: view!.sequence, approved: approve, rationale: why });
      await load(view!.sequence);
      setNotice(`${approve ? "Approved" : "Reopened"}: ${done.decided.join(", ") || "nothing to change"}` +
        (done.skipped.length ? ` · already so: ${done.skipped.join(", ")}` : ""));
    } catch (reason) { setError(String(reason)); } finally { setBusy(false); }
  }
  const animatic = view.animatics.find((item) => item.version === shown) ?? view.animatics[0];
  async function make() {
    setBusy(true); setError("");
    try {
      const made = await request<{ version: number }>("/api/storyboard/animatic", { sequence: view!.sequence });
      await load(view!.sequence); setShown(made.version);
    } catch (reason) { setError(String(reason)); } finally { setBusy(false); }
  }
  return <details className="sequence-storyboard" open>
    <summary><strong>Sequence · {label}</strong> · {drawn} of {view.shots.length} shots drawn · {view.seconds} s</summary>
    {view.sequences.length > 1 && <label>Sequence <select value={view.sequence} onChange={(event) => void load(event.target.value)}>
      {view.sequences.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>}
    <section aria-label="Animatic" className="sequence-animatic">
      {animatic ? <><video key={animatic.url} controls preload="metadata" src={encodeURI(animatic.url)} />
        <p className="prep-help">Animatic v{animatic.version}: each shot's current drawing for its breakdown duration.
          {view.animatics.length > 1 && <> Earlier: {view.animatics.slice(1).map((item) =>
            <button key={item.version} onClick={() => setShown(item.version)}>v{item.version}</button>)}</>}</p></>
        : <p>No animatic yet.</p>}
      <button disabled={busy} onClick={() => void make()}>{busy ? "Making the animatic…" : "Make a new animatic from the current drawings"}</button>
      {error && <p role="alert">{error}</p>}
    </section>
    {phases.length > 0 && <section aria-label="Storyboard approval" className="sequence-approval">
      <p><strong>{whole ? "Storyboard approved" : `Storyboard: ${approved.length} of ${phases.length} scenes approved`}</strong>
        {phases.some(([, item]) => item.changed_since) && <> · the breakdown changed since the approval of {phases
          .filter(([, item]) => item.changed_since).map(([id]) => id).join(", ")}</>}</p>
      <p className="prep-help">Approving says the sequence's storyboard is what will be produced; master images come next. It blocks nothing and can be reopened.</p>
      <button disabled={busy || drawn < view.shots.length && !whole} onClick={() => void decide(!whole)}>
        {whole ? "Reopen the sequence's storyboard" : "Approve the sequence's storyboard"}</button>
      {drawn < view.shots.length && !whole && <span className="prep-help"> Every shot needs a drawing first.</span>}
      {notice && <p role="status">{notice}</p>}
    </section>}
    <ol className="sequence-sheet" aria-label="Contact sheet">
      {view.shots.map((shot) => <li key={`${shot.scene}-${shot.shot}`}>
        <button onClick={() => onOpen?.(shot.scene, shot.shot)} title={`${shot.scene_title} · ${shot.seconds} s`}>
          {shot.image_url ? <img loading="lazy" src={encodeURI(shot.image_url)} alt={`${shot.scene} ${shot.shot}`} />
            : <span className="sequence-missing">no drawing yet</span>}
          <span>{shot.scene} {shot.shot}{shot.version ? ` · v${shot.version}` : ""} · {shot.seconds}s</span>
        </button></li>)}
    </ol>
    {view.shots.some((shot) => shot.master) && <MasterReview shots={view.shots} reload={() => load(view.sequence)} />}
  </details>;
}

function MasterReview({ shots, reload }: { shots: Shot[]; reload: () => Promise<void> }) {
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const withMaster = shots.filter((shot) => shot.master);
  const approved = withMaster.filter((shot) => shot.master!.state === "approved").length;
  const waiting = withMaster.filter((shot) => shot.master!.state === "waiting" && shot.master!.candidates.length
    && shot.master!.candidates[shot.master!.candidates.length - 1].frame_ok !== false);
  const failed = withMaster.filter((shot) => shot.master!.state === "failed").length;
  async function act(shot: Shot, outcome: string) {
    const master = shot.master!;
    const chosen = master.candidates[master.candidates.length - 1]?.path ?? "";
    let why = "";
    if (outcome === "changes_requested") {
      const answer = window.prompt(`${shot.scene} ${shot.shot}: what should the next version change?`);
      if (!answer) return;
      why = answer;
    }
    setBusy(shot.scene + shot.shot); setError("");
    try { await decideGate(shot.scene, master.gate, outcome, chosen, why); await reload(); }
    catch (reason) { setError(String(reason)); } finally { setBusy(""); }
  }
  async function retry(shot: Shot) {
    setBusy(shot.scene + shot.shot); setError("");
    try {
      // A new masters run for the scene: every picture already made is kept, only the missing ones are made.
      const response = await fetch("/api/commands", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: "start_workflow", scene_id: shot.scene, template: "masters",
          actor: { id: "director-gui", kind: "human" } }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body?.error?.message ?? `The runtime answered ${response.status}`);
      }
      await reload();
    } catch (reason) { setError(String(reason)); } finally { setBusy(""); }
  }
  async function approveAll() {
    if (!window.confirm(`Approve the latest picture of the ${waiting.length} shots waiting?`)) return;
    setBusy("all"); setError("");
    try {
      for (const shot of waiting) {
        const master = shot.master!;
        await decideGate(shot.scene, master.gate, "approved", master.candidates[master.candidates.length - 1].path, "");
      }
      await reload();
    } catch (reason) { setError(String(reason)); } finally { setBusy(""); }
  }
  return <section aria-label="Master images" className="sequence-masters">
    <h3>Master images · {approved} of {withMaster.length} approved{waiting.length ? ` · ${waiting.length} waiting for you` : ""}
      {failed ? ` · ${failed} refused by the generator` : ""}</h3>
    <p className="prep-help">Each shot's approved drawing, finished. Approve it, or ask for another version and say what to change; earlier versions are kept.</p>
    {waiting.length > 1 && <button disabled={!!busy} onClick={() => void approveAll()}>Approve every waiting picture in the film's frame ({waiting.length})</button>}
    {error && <p role="alert">{error}</p>}
    <ol className="sequence-master-grid">
      {withMaster.map((shot) => {
        const master = shot.master!;
        const latest = master.candidates[master.candidates.length - 1];
        const chosen = master.candidates.find((item) => item.path === master.chosen) ?? latest;
        return <li key={`${shot.scene}-${shot.shot}`} className={`master-${master.state}`}>
          <strong>{shot.scene} {shot.shot}</strong> · {master.state === "waiting" ? (latest ? "waiting for you" : "being made")
            : master.state === "approved" ? "approved" : master.state === "failed" ? "NOT MADE: the generator refused"
            : master.state === "making" ? (master.decided_by === "system" ? "being made again (wrong frame)" : "being made")
            : master.state.replace("_", " ")}
          <div className="master-pair">
            {shot.image_url && <img loading="lazy" src={encodeURI(shot.image_url)} alt={`${shot.scene} ${shot.shot} drawing`} title="The approved drawing" />}
            {(master.state === "approved" ? chosen : latest)
              ? <a href={encodeURI((master.state === "approved" ? chosen : latest)!.url)} target="_blank" rel="noreferrer">
                  <img loading="lazy" src={encodeURI((master.state === "approved" ? chosen : latest)!.url)} alt={`${shot.scene} ${shot.shot} master`} /></a>
              : <span className="sequence-missing">not made yet</span>}
          </div>
          {(() => { const shown = master.state === "approved" ? chosen : latest;
            return shown?.size ? <small className={shown.frame_ok ? "frame-ok" : "frame-off"}>
              {shown.size} · {shown.ratio}:1 {shown.frame_ok ? "· the film's frame" : "· NOT the film's frame"}</small> : null; })()}
          {master.candidates.length > 1 && <small> · {master.candidates.length} versions</small>}
          {master.state === "changes_requested" && master.decided_by === "system" &&
            <p className="prep-help">Being made again by the system: {master.rationale}</p>}
          {master.findings?.map((item, index) => <p key={index} className="prep-notice">{item}</p>)}
          {master.state === "failed" && <>
            <p className="prep-notice">{master.rationale}</p>
            <div className="master-actions"><button disabled={!!busy} onClick={() => void retry(shot)}>Try again</button></div></>}
          {master.state === "making" && master.rationale && <p className="prep-help">{master.rationale}</p>}
          {master.state === "waiting" && latest && <div className="master-actions">
            <button disabled={!!busy} onClick={() => void act(shot, "approved")}>Approve</button>
            <button disabled={!!busy} onClick={() => void act(shot, "changes_requested")}>Ask for another</button></div>}
        </li>;
      })}
    </ol>
  </section>;
}
