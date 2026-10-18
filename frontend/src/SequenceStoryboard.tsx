// The sequence as the director reviews it (Demo 01, 2026-10-18): every shot's current drawing in order,
// as a contact sheet, and the storyboard animatic -- the drawings held for their breakdown durations.
import { useEffect, useState } from "react";
import { request } from "./creation.ts";
import "./sequence-storyboard.css";

interface Shot { scene: string; scene_title: string; shot: string; seconds: number; board: string | null; version: number | null; image_url: string }
interface View {
  sequences: { id: string; label: string }[]; sequence: string; shots: Shot[]; seconds: number;
  animatics: { version: number; url: string }[];
}

export function SequenceStoryboard({ onOpen }: { onOpen?: (scene: string, shot: string) => void }) {
  const [view, setView] = useState<View | null>(null);
  const [sequence, setSequence] = useState("");
  const [shown, setShown] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
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
    <ol className="sequence-sheet" aria-label="Contact sheet">
      {view.shots.map((shot) => <li key={`${shot.scene}-${shot.shot}`}>
        <button onClick={() => onOpen?.(shot.scene, shot.shot)} title={`${shot.scene_title} · ${shot.seconds} s`}>
          {shot.image_url ? <img loading="lazy" src={encodeURI(shot.image_url)} alt={`${shot.scene} ${shot.shot}`} />
            : <span className="sequence-missing">no drawing yet</span>}
          <span>{shot.scene} {shot.shot}{shot.version ? ` · v${shot.version}` : ""} · {shot.seconds}s</span>
        </button></li>)}
    </ol>
  </details>;
}
