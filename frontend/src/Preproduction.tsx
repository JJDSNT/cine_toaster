import { useEffect, useRef, useState } from "react";
import { addressOf, type Navigation } from "./navigation.ts";
import type { Seen } from "./Assistant.tsx";
import { focusSearch, mediaAddress, resolveFocus, type Focus } from "./preproduction.ts";
import { drawingPreview, drawingVersions, type StoryDrawings } from "./storyboard.ts";
import { StoryDrawing } from "./StoryDrawing.tsx";
import { request, type CreationState } from "./creation.ts";
import { ShotPlanning } from "./ShotPlanning.tsx";
import { InceptionReview } from "./InceptionReview.tsx";
import { DecisionLink } from "./DecisionInbox.tsx";

interface Unit { index: number; kind: string; text: string; speaker?: string; shots: string[] }
interface Frame { shot_id: string; label: string; still: string; duration_seconds: number }
interface Scene {
  id: string; title: string; summary: string; frames: Frame[];
  script: { linked: boolean; heading: string; units: Unit[] } | null;
}
interface Writing { title: string; screenplay: string; scenes: Scene[] }
interface Detail {
  phase?: { phase: string; changed_since?: boolean };
  shots: { id: string; cut?: { type: string; reason?: string }; camera?: string }[];
}
interface Board { path: string; stale: boolean; version: number }
interface Boards {
  scene: string;
  shots: Record<string, { label: string; boards: { start?: Board; end?: Board } }>;
  "animatic.mp4"?: string;
}
type AssistantState = "checking" | "available" | "off" | "unavailable";

async function read<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
  return response.json() as Promise<T>;
}

export function Preproduction() {
  const [writing, setWriting] = useState<Writing | null>(null);
  const [error, setError] = useState("");
  const [focus, setFocus] = useState<Focus>({ scene: "", shot: "", study: false });
  const [detail, setDetail] = useState<Detail | null>(null);
  const [boards, setBoards] = useState<Boards | null>(null);
  const [sceneError, setSceneError] = useState("");
  const [boardError, setBoardError] = useState("");
  const [drawings, setDrawings] = useState<StoryDrawings | null>(null);
  const [drawingError, setDrawingError] = useState("");
  const [candidate, setCandidate] = useState(() => new URLSearchParams(window.location.search).get("candidate") ?? "");
  const [assistant, setAssistant] = useState<AssistantState>("checking");
  const [talking, setTalking] = useState(false);
  const [assistantReady, setAssistantReady] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [creation, setCreation] = useState<CreationState | null>(null);
  const [planningError, setPlanningError] = useState("");
  const [continuation, setContinuation] = useState<{ decisionId: string; attempt?: string } | null>(null);
  const assistantFrame = useRef<HTMLIFrameElement>(null);

  async function reloadCreation() {
    try { setCreation(await request<CreationState>("/api/creation")); setPlanningError(""); }
    catch (reason) { setPlanningError(String(reason)); }
  }
  useEffect(() => { void reloadCreation(); }, [refresh]);

  useEffect(() => {
    const controller = new AbortController();
    setError("");
    read<Writing>("/api/writing", controller.signal).then((data) => {
      setWriting(data);
      setFocus(resolveFocus(data.scenes, window.location.search));
    }).catch((reason: Error) => { if (!controller.signal.aborted) setError(reason.message); });
    return () => controller.abort();
  }, [refresh]);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/copilotkit/info", { signal: controller.signal }).then(async (response) => {
      if (response.ok) { setAssistant("available"); return; }
      const data = await response.json().catch(() => null);
      setAssistant(data?.error?.code === "assistant_off" ? "off" : "unavailable");
    }).catch(() => { if (!controller.signal.aborted) setAssistant("unavailable"); });
    return () => controller.abort();
  }, [refresh]);

  useEffect(() => {
    if (!writing) return;
    const onBack = () => {
      setFocus(resolveFocus(writing.scenes, window.location.search));
      setCandidate(new URLSearchParams(window.location.search).get("candidate") ?? "");
    };
    window.addEventListener("popstate", onBack);
    return () => window.removeEventListener("popstate", onBack);
  }, [writing]);

  useEffect(() => {
    const controller = new AbortController();
    setDrawingError("");
    read<StoryDrawings>("/api/storyboard", controller.signal).then(setDrawings)
      .catch((reason: Error) => { if (!controller.signal.aborted) { setDrawings(null); setDrawingError(reason.message); } });
    return () => controller.abort();
  }, [refresh]);

  useEffect(() => {
    setDetail(null); setBoards(null); setSceneError(""); setBoardError("");
    if (!focus.scene) return;
    const controller = new AbortController();
    read<Detail>(`/api/scene?id=${encodeURIComponent(focus.scene)}`, controller.signal)
      .then(setDetail).catch((reason: Error) => { if (!controller.signal.aborted) setSceneError(reason.message); });
    read<Boards>(`/api/boards?scene=${encodeURIComponent(focus.scene)}`, controller.signal)
      .then(setBoards).catch((reason: Error) => { if (!controller.signal.aborted) setBoardError(reason.message); });
    return () => controller.abort();
  }, [focus.scene, refresh]);

  const scene = writing?.scenes.find((item) => item.id === focus.scene);
  const frame = scene?.frames.find((item) => item.shot_id === focus.shot);
  const shot = detail?.shots.find((item) => item.id === focus.shot);
  const study = boards?.scene === focus.scene ? boards.shots[focus.shot] : undefined;
  const sceneURL = `/?scene=${encodeURIComponent(focus.scene)}`;
  const versions = drawingVersions(drawings, focus.scene, focus.shot);
  const drawing = drawingPreview(versions, candidate);
  const coverage = drawings?.coverage.find((item) => item.scene === focus.scene);

  function select(next: Focus, version?: string) {
    const picked = version ?? (next.scene === focus.scene && next.shot === focus.shot ? candidate : "");
    const search = focusSearch(next) + (picked ? `&candidate=${encodeURIComponent(picked)}` : "");
    if (search !== window.location.search) window.history.pushState(null, "", search);
    setCandidate(picked);
    setFocus(next);
  }

  useEffect(() => {
    const receive = (event: MessageEvent) => {
      if (event.origin !== window.location.origin || event.source !== assistantFrame.current?.contentWindow) return;
      if (event.data?.type === "cine-toaster:assistant-ready") setAssistantReady(true);
      if (event.data?.type === "cine-toaster:production-update") setRefresh((n) => n + 1);
      if (event.data?.type === "cine-toaster:highlight") {
        const selected = scene?.frames.find((item) => item.shot_id === event.data.shot);
        if (selected) select({ ...focus, shot: selected.shot_id });
      }
      if (event.data?.type === "cine-toaster:navigate" && event.data.where) {
        const where = event.data.where as Navigation;
        // Navigate only through the existing same-origin route resolver.
        window.location.assign(addressOf(where));
      }
    };
    window.addEventListener("message", receive);
    return () => window.removeEventListener("message", receive);
  });

  useEffect(() => {
    if (assistantReady && talking && continuation) assistantFrame.current?.contentWindow?.postMessage({
      type: "cine-toaster:continue-inception", ...continuation,
    }, window.location.origin);
  }, [assistantReady, talking, continuation]);

  useEffect(() => {
    if (!assistantReady || !talking) return;
    assistantFrame.current?.contentWindow?.postMessage({
      type: "cine-toaster:context",
      seen: {
        room: "screenplay and storyboard", scene: focus.scene, focus: focus.shot, selected: focus.shot,
        details: JSON.stringify({
          selected_intent: frame?.label ?? "", composition_study: focus.study,
          shot_still_present: Boolean(frame?.still),
          storyboard_candidate: drawing?.id ?? null, declared_inputs: drawing?.inputs ?? [],
          candidate_findings: drawing?.findings ?? [], candidate_approval: "not recorded",
          storyboard_phase: detail?.phase ?? "unknown", visual_review: "not established by this view",
        }),
      } satisfies Seen,
    }, window.location.origin);
  }, [assistantReady, talking, focus, frame, detail, drawing]);

  if (!writing) return <main className="prep-loading"><h1>Screenplay & Storyboard</h1>
    {error ? <><p role="alert">{error}</p><button onClick={() => setRefresh((n) => n + 1)}>Retry</button></>
      : <p role="status">Opening the production…</p>}<a href="/">Control Room</a></main>;

  return <div className="prep-shell">
    <header className="prep-header">
      <div><span className="prep-eyebrow">CINE TOASTER · PRE-PRODUCTION PILOT</span><h1>{writing.title}</h1>
        <p>{scene ? `${scene.id} · ${scene.title}${frame ? ` / ${frame.shot_id}` : ""}` : "No scene breakdown yet"}</p></div>
      <div className="prep-actions"><button onClick={() => setRefresh((n) => n + 1)}>Refresh</button>
        <button aria-expanded={talking} onClick={() => { setTalking(!talking); }}>Assistant · {assistant}</button></div>
    </header>
    <nav className="prep-workspaces" aria-label="Workspaces">
      <DecisionLink />
      <a href="/app/creation.html">Creation / Inception</a>
      <span aria-current="page">Screenplay & Storyboard</span>
      <a href={scene ? sceneURL : "/?view=scenes"}>Production ↗</a>
      <a href="/?view=sequences">Assembly & versions ↗</a>
      <a href="/">Control Room</a><a href="/app/">Canvas</a>
    </nav>
    {error && <p className="prep-notice" role="alert">Refresh failed: {error}. Displaying the last loaded records.</p>}
    <div className="prep-body">
      <aside className="prep-scenes" aria-label="Scenes"><h2>Scenes</h2>
        {writing.scenes.map((item) => <button key={item.id} aria-current={item.id === focus.scene ? "true" : undefined}
          onClick={() => select({ scene: item.id, shot: item.frames[0]?.shot_id ?? "", study: false })}>
          <small>{item.id}</small><strong>{item.title}</strong><span>{item.frames.length} proposed shots</span></button>)}
        {!writing.scenes.length && <p>No breakdowns exist yet.</p>}
      </aside>
      <main className="prep-work" id="prep-work">
        <section className="prep-status" aria-label="Review state">
          <div><strong>{scene?.title ?? "Start with the screenplay"}</strong>
            <p>{scene?.summary ?? "Read or edit the screenplay, then define the scene's proposed shots."}</p></div>
          <div><span className="prep-badge">{detail?.phase?.phase === "production"
            ? detail.phase.changed_since ? "Changed since storyboard approval" : "Storyboard approval recorded"
            : detail ? "Storyboard not approved" : "Approval state not loaded"}</span>
            <p>{scene ? `${coverage ? `${coverage.with_candidates}/${coverage.shots} storyboard candidates · ` : ""}${scene.frames.filter((item) => item.still).length} separate discovered stills · review not established here`
              : "No storyboard to review yet"}</p></div>
        </section>
        {drawings && <p className="prep-help" role="status">{coverage ? `${coverage.with_candidates}/${coverage.shots} shots in this scene have storyboard candidates. ` : ""}
          Whole film: {drawings.coverage.reduce((sum, item) => sum + item.with_candidates, 0)}/{drawings.coverage.reduce((sum, item) => sum + item.shots, 0)} shots have candidates · not an approval count.</p>}
        <details className="prep-journey"><summary>How this develops: story drawing → 3D study → shot master</summary>
          <p>Story drawings explore action and narrative. 3D blockouts test camera, space and movement; the animatic checks timing.
            A shot master develops the intended finished look with suitable cast/style references. Each result retains its own inputs and versions; no automatic conversion or approval is implied.</p>
          <p>A cast master reference establishes identity; it is not the shot master. A still is a static image or rendered frame, not necessarily another production stage.
            The full handoff to master generation is not implemented in this pilot.</p>
        </details>
        {scene && <p className="prep-help">Next review: read the scene against its proposed shots, inspect the visual evidence and identify what still needs a candidate or a decision.</p>}
        {planningError && <p role="alert">Could not refresh directing records: {planningError}</p>}
        {creation && scene && <ShotPlanning data={creation} scene={scene.id} />}
        {creation && scene && creation.inception_review?.current?.proposal.direction_plan &&
          creation.directing?.plans.some((plan) => plan.id === creation.inception_review?.current?.proposal.direction_plan && plan.scene === scene.id) &&
          <InceptionReview data={creation} title="Shot proposal · your direction" reload={reloadCreation}
            onDecision={(decisionId, attempt) => { setContinuation({ decisionId, attempt }); setTalking(true); }} />}
        <div className="prep-columns">
          <section className="prep-script" aria-label="Screenplay"><div className="prep-section-heading"><h2>Screenplay</h2>
            <a href="/app/script.html">Edit screenplay ↗</a></div>
            <p className="prep-help">Select a passage to see its proposed shot. Text is read from the production.</p>
            {scene?.script?.linked ? scene.script.units.map((unit) => <article key={unit.index}
              className={`prep-unit ${unit.shots.includes(focus.shot) ? "selected" : ""}`}>
              {unit.kind === "heading" ? <h3>{unit.text}</h3> : <>
                {unit.speaker && <strong>{unit.speaker}</strong>}<p>{unit.text}</p>
                <div className="prep-unit-links">{unit.shots.map((id) => <button key={id}
                  aria-pressed={id === focus.shot} onClick={() => select({ ...focus, shot: id })}>{id}</button>)}
                  {!unit.shots.length && <span>Not covered by a proposed shot</span>}</div></>}
            </article>) : <><p className="prep-notice">{scene ? "This scene is not linked to the screenplay. Full screenplay below." : "Full screenplay"}</p>
              <pre>{writing.screenplay || "No screenplay text yet."}</pre></>}
          </section>
          <section className="prep-board" aria-label="Storyboard"><div className="prep-section-heading"><h2>Storyboard</h2>
            <a href="/?view=storyboard">Whole film ↗</a></div>
            <p className="prep-help">Proposed shots in order. A composition study and a shot still have different purposes.</p>
            <nav className="prep-shots" aria-label="Proposed shots">{scene?.frames.map((item) => <button key={item.shot_id}
              aria-pressed={item.shot_id === focus.shot} onClick={() => select({ ...focus, shot: item.shot_id })}>
              {drawingVersions(drawings, scene.id, item.shot_id)[0]?.image_available && <img loading="lazy"
                src={mediaAddress(drawingVersions(drawings, scene.id, item.shot_id)[0].image.path)} alt="" />}
              <strong>{item.shot_id}</strong><span>{item.duration_seconds}s</span></button>)}</nav>
            {frame ? <>
              <h3>{frame.shot_id} · {frame.label}</h3>
              <div className="prep-modes" aria-label="Visual purpose">
                <button aria-pressed={!focus.study} onClick={() => select({ ...focus, study: false })}>Shot visual</button>
                <button aria-pressed={focus.study} onClick={() => select({ ...focus, study: true })}>Composition study</button>
              </div>
              {focus.study ? <>
                {boardError ? <p role="alert">Could not read studies: {boardError}</p> : !boards ? <p role="status">Loading studies…</p>
                  : study?.boards.start ? <figure><img src={`${mediaAddress(study.boards.start.path)}?v=${study.boards.start.version}`}
                    alt={`${frame.shot_id} clay composition at the start`} /><figcaption>Computed clay composition · {study.boards.start.stale ? "Plan changed since render" : "Matches recorded plan fingerprint"}</figcaption></figure>
                    : <div className="prep-empty"><strong>No composition study for this shot</strong><p>You can review its visual intent before a measured layout exists.</p></div>}
                <p className="prep-notice">Clay mannequins test framing and movement. They do not establish acting, sleeping/sitting poses, flight height or the finished visual style.</p>
                {study?.boards.end && <details><summary>End composition{study.boards.end.stale ? " · plan changed" : ""}</summary>
                  <img className="prep-study-end" src={mediaAddress(study.boards.end.path)} alt={`${frame.shot_id} end composition`} /></details>}
                {boards?.["animatic.mp4"] && <details><summary>Scene composition preview · {scene?.title}</summary>
                  <video key={boards["animatic.mp4"]} controls preload="metadata" src={mediaAddress(boards["animatic.mp4"]!)} />
                  <p>Recorded scene preview. Its currency is not verified by the still-board fingerprints.</p></details>}
              </> : <>
                {drawingError ? <p role="alert">Could not read storyboard candidates: {drawingError}</p>
                  : !drawings ? <p role="status">Loading storyboard drawings…</p>
                  : <StoryDrawing versions={versions} candidate={candidate} choose={(id) => select(focus, id)} />}
                {frame.still && <details><summary>Separate discovered shot still</summary><figure><img src={mediaAddress(frame.still)} alt={`${frame.shot_id} discovered shot still`} />
                  <figcaption>Discovered shot still · purpose and approval must be checked in its source records.</figcaption></figure></details>}
              </>}
              <dl className="prep-facts"><dt>Planned duration</dt><dd>{frame.duration_seconds} seconds</dd>
                <dt>Join into shot</dt><dd>{shot?.cut ? `${shot.cut.type}${shot.cut.reason ? ` · ${shot.cut.reason}` : ""}`
                  : detail ? "No cut record for this shot" : "Loading shot details…"}</dd></dl>
              <div className="prep-links"><a href={sceneURL}>Open scene tools ↗</a><a href="/?view=cast">Cast</a>
                <a href="/?view=locations">Locations</a><a href="/?view=styles">Styles</a><a href="/?view=library">Production files & references ↗</a></div>
              {sceneError && <p role="alert">Could not read scene details: {sceneError}</p>}
            </> : <p className="prep-empty">This scene has no proposed shots yet.</p>}
          </section>
        </div>
      </main>
      {talking && <aside className="prep-assistant" aria-label="Directing assistant"><div className="prep-section-heading"><h2>Assistant</h2>
        <button onClick={() => { setTalking(false); setAssistantReady(false); }}>Close</button></div>
        {assistant === "available" ? <iframe ref={assistantFrame} title="Directing assistant" src="/app/assistant.html"
          onLoad={() => setAssistantReady(true)} /> : <><p role="status">{assistant === "off" ? "The assistant is off for this server session."
            : assistant === "checking" ? "Checking assistant availability…" : "The assistant service could not be reached."}</p>
            <p>Enable the assistant when launching Cine Toaster with <code>toast serve &lt;film&gt; --assistant</code>. You can continue reviewing the film here.</p>
            <button onClick={() => setRefresh((n) => n + 1)}>Check again</button></>}
      </aside>}
    </div>
  </div>;
}
