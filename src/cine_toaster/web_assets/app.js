import { drawBlockout } from "./blockout.js";
import { renderCompare } from "./compare.js";
import { startAssistant, tellAssistant } from "./assistant-drawer.js";
import { sentDetails, sentView } from "./sent.js";
import { renderVersions } from "./versions.js";
import { api, button, byId, el, label, metric, runCommand, sectionHeading, statusPill, toast } from "./ui.js";

const state = {
  project: null,
  production: null,
  transitions: [],
  currentView: "overview",
  libraryPath: null,
  sceneId: null,
  shotId: null,
  events: [],
  knowledge: null,
  writing: null,
};

const ROOMS = new Set([
  "overview", "script", "storyboard", "dialogue",
  "sequences", "scenes", "review", "cut", "cast", "locations",
  "transitions", "moves", "titles", "vfx", "sounds", "library", "knowledge",
]);

/** Write where we are into the address bar.
 *
 * Without this the back button leaves the application, a reload loses the
 * room, and a scene cannot be sent to anyone. The app already read `view`,
 * `scene` and `shot` from the URL on boot; it simply never wrote them.
 */
function addressFor({ view, scene, shot }) {
  const parameters = new URLSearchParams();
  if (shot && scene) {
    parameters.set("scene", scene);
    parameters.set("shot", shot);
  } else if (scene) {
    parameters.set("scene", scene);
  } else if (view && view !== "overview") {
    parameters.set("view", view);
  }
  const query = parameters.toString();
  return query ? `?${query}` : window.location.pathname;
}

function remember({ view, scene = null, shot = null }, { replace = false } = {}) {
  const address = addressFor({ view, scene, shot });
  const entry = { view, scene, shot };
  if (replace || window.location.search === new URL(address, window.location.href).search) {
    window.history.replaceState(entry, "", address);
  } else {
    window.history.pushState(entry, "", address);
  }
}

function highlight(view) {
  document.querySelectorAll("[data-view]").forEach((node) => {
    node.classList.toggle("active", node.dataset.view === view);
  });
}

function draw(view) {
  if (view === "overview") renderOverview();
  else if (view === "script") renderScript();
  else if (view === "storyboard") renderStoryboard();
  else if (view === "dialogue") renderDialogue();
  else if (view === "sequences") renderSequences();
  else if (view === "scenes") renderScenes();
  else if (view === "review") renderReview();
  else if (view === "cut") renderCut();
  else if (view === "transitions") renderTransitions();
  else if (view === "moves") renderMoves();
  else if (view === "locations") renderLocations();
  else if (view === "titles") renderTitles();
  else if (view === "vfx") renderVfx();
  else if (view === "sounds") renderSounds();
  else if (view === "cast") renderCast();
  else if (view === "library") renderLibrary(state.project.id);
  else if (view === "knowledge") renderKnowledge();
  byId("workspace").focus();
  state.scene = null;
  tellAssistant();
}

function setView(view, { record = true } = {}) {
  state.currentView = view;
  state.sceneId = null;
  state.shotId = null;
  highlight(view);
  if (record) remember({ view });
  draw(view);
}

function phaseRail(phases) {
  const rail = el("div", "phase-rail");
  for (const phase of phases) {
    const card = el("article", `phase-card phase-${phase.status}`);
    const top = el("div", "phase-top");
    top.append(el("strong", "", phase.label), statusPill(phase.status));
    const bar = el("div", "progress-track");
    const fill = el("span", "progress-fill");
    fill.style.width = `${phase.progress}%`;
    bar.append(fill);
    card.append(top, bar, el("small", "", `${phase.progress}%`));
    rail.append(card);
  }
  return rail;
}

function renderOverview() {
  const production = state.production;
  if (!production) return renderUnstructured();
  const root = byId("workspace");
  root.replaceChildren();

  const hero = el("section", "overview-hero");
  const heroCopy = el("div");
  heroCopy.append(
    el("span", "eyebrow", "PRODUCTION OVERVIEW"),
    el("h1", "", production.title),
    el("p", "hero-logline", production.logline),
  );
  const target = el("div", "target-card");
  target.append(
    el("span", "eyebrow", "NEXT TARGET"),
    el("strong", "", production.production.target || "Not set"),
    el("small", "", production.production.target_date || "No date"),
  );
  hero.append(heroCopy, target);

  const metrics = el("section", "metric-grid");
  metrics.append(
    metric(`${production.metrics.overall_progress}%`, "Production progress", "Across scene workflows"),
    metric(production.metrics.total_scenes, "Scenes", `${production.metrics.approved_scenes} approved`),
    metric(production.metrics.in_progress_scenes, "In motion", "Currently moving through the pipeline"),
    metric(production.metrics.attention_items, "Need attention", "Reviews, decisions, and blockers"),
  );

  const phases = el("section", "panel wide-panel");
  phases.append(sectionHeading("PHASES", "Production map", "A high-level view; each room will grow its own tools."));
  phases.append(phaseRail(production.phases));

  const columns = el("section", "overview-columns");
  const focusPanel = el("article", "panel");
  focusPanel.append(sectionHeading("NOW", "Current focus"));
  if (production.active_scene) focusPanel.append(sceneFocus(production.active_scene));

  const attentionPanel = el("article", "panel");
  attentionPanel.append(sectionHeading("QUEUE", "Requires you", "Only work that needs a human decision."));
  const queue = el("div", "attention-list");
  for (const item of production.attention) {
    const row = button("", () => renderScene(item.scene_id), "attention-row");
    row.append(
      el("span", `attention-icon attention-${item.kind}`, item.kind === "blocker" ? "!" : "?"),
      el("strong", "", `${item.scene_id} · ${item.scene_title}`),
      el("small", "", item.message),
      el("b", "", "→"),
    );
    queue.append(row);
  }
  if (!production.attention.length) queue.append(el("p", "empty-state", "Nothing needs attention."));
  attentionPanel.append(queue);
  columns.append(focusPanel, attentionPanel);

  const sceneStrip = el("section", "panel wide-panel");
  const stripHeading = sectionHeading("SCENES", "Production line", "Move through the film by creative unit, not by directory.");
  stripHeading.append(button("All scenes →", () => setView("scenes")));
  sceneStrip.append(stripHeading, compactSceneList(production.scenes));
  root.append(hero, metrics, phases, columns, sceneStrip, renderActivity());
}

// What has actually happened, newest first. Committed decisions only: this is
// not a log of everything the software did.
function renderActivity() {
  const panel = el("section", "panel wide-panel");
  panel.append(
    sectionHeading("ACTIVITY", "Recent decisions", "Every committed choice, whoever made it."),
  );
  const list = el("div", "activity-list");
  for (const event of state.events.slice(0, 12)) {
    const payload = event.payload || {};
    const row = payload.shot_id
      ? button("", () => openCompare(payload.scene_id, payload.shot_id), "activity-row")
      : el("div", "activity-row");
    const when = String(event.occurred_at || "").slice(11, 19);
    const headline = event.type === "take.cleared"
      ? `${payload.shot_id} cleared`
      : `${payload.shot_id} → ${payload.take_id}`;
    row.append(
      el("span", "activity-time", when),
      el("strong", "", headline),
      el("small", "muted", `${payload.actor?.id || "unknown"}${payload.rationale ? ` · ${payload.rationale}` : ""}`),
    );
    list.append(row);
  }
  if (!state.events.length) list.append(el("p", "empty-state", "No decisions recorded yet."));
  panel.append(list);
  return panel;
}

function sceneFocus(scene) {
  const card = el("div", "focus-card");
  const title = el("div", "focus-title");
  title.append(el("span", "scene-id", scene.id), statusPill(scene.status));
  card.append(title, el("h3", "", scene.title), el("p", "", scene.summary));
  const progress = el("div", "focus-progress");
  progress.append(el("span", "", `${label(scene.current_step)} · iteration ${scene.iteration}`), el("strong", "", `${scene.progress}%`));
  card.append(progress, button("Open scene workspace", () => renderScene(scene.id), "primary-button"));
  return card;
}

function compactSceneList(scenes) {
  const list = el("div", "scene-strip");
  for (const scene of scenes) {
    const card = button("", () => renderScene(scene.id), "scene-chip");
    card.append(
      el("span", "scene-id", scene.id),
      el("strong", "", scene.title),
      el("small", "", label(scene.current_step)),
      el("i", `scene-state scene-state-${scene.status}`),
    );
    list.append(card);
  }
  return list;
}

// A sequence is what the production actually judges as finished or not: a run
// of scenes assembled and reviewed together. Scenes hold the detail; this is
// where someone says "this part works now".
// Versions of a sequence (phase 2): each an assembled cut from its scenes'
// versions, kept, watchable and judged. Made in the background and adopted
// from the jobs tray, like a scene's.
function renderSequenceVersions(sequence) {
  const box = el("div", "sequence-versions");
  if (sequence.id === "unassigned") return box;
  const assemble = button("Assemble a new version from the scenes' versions", async () => {
    assemble.disabled = true;
    try {
      const job = await startJob("assemble_sequence", { sequence: sequence.id });
      toastMessage(`Assembling ${job.params.version}. Adopt it from the jobs tray when it is ready.`);
    } catch (error) {
      alert(error.message);
    } finally {
      assemble.disabled = false;
    }
  }, "quiet-button");
  box.append(assemble);
  for (const version of sequence.versions || []) {
    const card = el("article", `sequence-version verdict-${version.verdict}`);
    const head = el("div", "sequence-version-head");
    head.append(el("strong", "", version.id), statusPill(version.verdict === "pending" ? "in_review" : version.verdict),
      el("small", "muted", `${Math.round(version.duration_seconds)}s · ${Object.entries(version.scenes).map(([scene, v]) => `${scene} ${v}`).join(", ")}`));
    card.append(head);
    const video = el("video");
    video.src = `/media/${version.media}`;
    video.controls = true;
    video.preload = "none";
    card.append(video, el("p", "muted", version.summary));
    const actions = el("div", "job-actions");
    for (const [verdict, label] of [["approved", "Approve"], ["rejected", "Reject"]]) {
      if (version.verdict === verdict) continue;
      actions.append(button(label, async () => {
        const response = await fetch("/api/sequence-review", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sequence_id: sequence.id, version_id: version.id, verdict }),
        });
        const payload = await response.json();
        if (!response.ok) return alert(payload.error?.message || "Could not record the verdict");
        await refreshFromEvent({ type: "sequence.version.reviewed" });
      }, "blockout-chip"));
    }
    card.append(actions);
    box.append(card);
  }
  return box;
}

function toastMessage(text) {
  const note = el("div", "toast-note", text);
  document.body.append(note);
  setTimeout(() => note.remove(), 4000);
}

// The cast (SPEC-0003, CT-0040): each character declared once -- the picture
// that makes them, the variants the story needs, the voice they always have --
// and where they appear, with how their voice sounds in each scene.
function renderCast() {
  if (!state.production) return renderUnstructured();
  const root = byId("workspace");
  root.replaceChildren();
  const heading = sectionHeading("CAST", "Who is in the film", "Each character once: their picture, their variants, their voice, and every scene they are in.");
  heading.classList.add("page-heading");
  root.append(heading);
  const members = Object.values(state.production.cast || {});
  if (!members.length) {
    root.append(el("p", "empty-state",
      "No cast sheets yet (cast/<id>/character.yaml). To draft them from what the scenes already say, without writing anything: toast cast propose <project>"));
    return;
  }
  const grid = el("div", "cast-grid");
  for (const member of members) {
    const card = el("article", "cast-card");
    const picture = el("div", "cast-picture");
    const master = member.references.find((ref) => ref.role === "master" && ref.exists);
    if (master) {
      const image = el("img");
      image.src = `/media/${master.path}`;
      image.alt = member.label;
      picture.append(image);
    } else {
      picture.append(el("span", "muted", member.authoritative_for.includes("face") ? "No master picture" : "Voice only"));
    }
    card.append(picture);
    const body = el("div", "cast-body");
    const title = el("div", "cast-title");
    title.append(el("strong", "", member.label), el("small", "muted", [member.id, ...(member.names || [])].join(" · ")));
    body.append(title);
    const decides = el("div", "tag-list");
    member.authoritative_for.forEach((item) => decides.append(el("span", "tag", item)));
    body.append(decides);
    if (member.description) body.append(el("p", "", member.description));
    if (member.voice) {
      const voice = el("div", "cast-voice");
      voice.append(el("span", "eyebrow", "VOICE"), el("p", "", member.voice.described || "—"));
      if (member.voice.language) voice.append(el("small", "muted", member.voice.language));
      for (const recording of member.voice.references || []) {
        const audio = el("audio");
        audio.src = `/media/${recording}`;
        audio.controls = true;
        audio.preload = "none";
        voice.append(audio);
      }
      body.append(voice);
    }
    const variants = Object.entries(member.variants || {});
    if (variants.length) {
      const list = el("div", "cast-variants");
      list.append(el("span", "eyebrow", "VARIANTS"));
      for (const [name, variant] of variants) {
        const row = el("div", "cast-variant");
        const ref = (variant.references || []).find((item) => item.role === "master" && item.exists);
        if (ref) {
          const image = el("img");
          image.src = `/media/${ref.path}`;
          image.alt = name;
          row.append(image);
        }
        row.append(el("b", "", name), el("small", "muted", variant.description || ""));
        list.append(row);
      }
      body.append(list);
    }
    const scenes = el("div", "cast-scenes");
    scenes.append(el("span", "eyebrow", `IN ${member.appearances.length} SCENE${member.appearances.length === 1 ? "" : "S"}`));
    for (const seen of member.appearances) {
      const row = button("", () => renderScene(seen.scene), "cast-scene");
      row.append(el("b", "", seen.scene), el("span", "", seen.title),
        el("small", "muted", [seen.shots.join(", "), seen.variant && `as ${seen.variant}`, seen.voice_state && `voice: ${seen.voice_state}`].filter(Boolean).join(" · ")));
      scenes.append(row);
    }
    body.append(scenes);
    for (const problem of member.problems || []) body.append(el("p", "join-finding warning", problem));
    card.append(body);
    grid.append(card);
  }
  root.append(grid);
}

function renderSequences() {
  if (!state.production) return renderUnstructured();
  const root = byId("workspace");
  root.replaceChildren();
  const heading = sectionHeading(
    "SEQUENCES",
    "The film in the parts you review",
    "Each sequence carries its own assembly and its own verdict.",
  );
  heading.classList.add("page-heading");
  root.append(heading);

  for (const sequence of state.production.sequences) {
    const panel = el("section", "panel wide-panel");
    const panelHeading = sectionHeading(
      sequence.act || sequence.id.toUpperCase(),
      sequence.label,
      `${sequence.scene_count} scenes · ${Math.round(sequence.duration_seconds)}s`,
    );
    panel.append(panelHeading);

    const facts = el("div", "sequence-facts");
    facts.append(
      metric(`${sequence.progress}%`, "Shots decided"),
      metric(String(sequence.pending_shots), "Awaiting a choice"),
      metric(String(sequence.open_findings), "Continuity notes"),
    );
    panel.append(facts);

    panel.append(renderSequenceVersions(sequence));

    if (sequence.render) {
      const assembly = el("div", "sequence-assembly");
      const video = el("video");
      video.src = `/media/${sequence.render}`;
      video.controls = true;
      video.preload = "metadata";
      assembly.append(video, el("small", "muted", sequence.render));
      panel.append(assembly);
    }

    const list = el("div", "shot-list");
    for (const sceneId of sequence.scene_ids) {
      const scene = state.production.scenes.find((item) => item.id === sceneId);
      if (!scene) continue;
      const row = button("", () => renderScene(scene.id), "shot-row shot-row-open");
      const copy = el("span", "shot-copy");
      copy.append(el("b", "", scene.id), el("strong", "", scene.title));
      row.append(
        copy,
        statusPill(scene.status),
        el("span", "take-count", `${scene.pending_shots.length} open`),
        el("strong", "selected-take", `${scene.progress}%`),
      );
      list.append(row);
    }
    panel.append(list);
    root.append(panel);
  }
  if (!state.production.sequences.length) {
    root.append(
      el(
        "p",
        "empty-state",
        "No sequences declared. Add [[sequences]] to project.toml to group scenes into reviewable parts.",
      ),
    );
  }
}

function renderScenes() {
  if (!state.production) return renderUnstructured();
  const root = byId("workspace");
  root.replaceChildren();
  const heading = sectionHeading("SCENE CONTROL", "Scenes", "Every scene, its current gate, iteration, and next action.");
  heading.classList.add("page-heading");
  root.append(heading);

  const table = el("div", "scene-table");
  const header = el("div", "scene-row scene-row-header");
  for (const value of ["Scene", "Status", "Current gate", "Iteration", "Progress", "Updated"]) header.append(el("span", "", value));
  table.append(header);
  for (const scene of state.production.scenes) {
    const row = button("", () => renderScene(scene.id), "scene-row");
    const identity = el("span", "scene-identity");
    identity.append(el("b", "", scene.id), el("strong", "", scene.title), el("small", "", scene.sequence));
    const progress = el("span", "table-progress");
    const bar = el("i", "progress-track");
    const fill = el("i", "progress-fill");
    fill.style.width = `${scene.progress}%`;
    bar.append(fill);
    progress.append(bar, el("small", "", `${scene.progress}%`));
    row.append(identity, statusPill(scene.status), el("span", "", label(scene.current_step)), el("span", "", `R${String(scene.iteration).padStart(2, "0")}`), progress, el("span", "muted", scene.updated_at));
    table.append(row);
  }
  root.append(table);
}

// The phase gate (production-flow.md): fitting the storyboard, or producing
// what it defines. Approving is the director's act; nothing is blocked by it.
function phaseLine(scene) {
  const phase = scene.phase || { phase: "fitting" };
  const line = el("div", "phase-line");
  const producing = phase.phase === "production";
  line.append(el("span", `status status-${producing ? "approved" : "planned"}`,
    producing ? "Production: storyboard approved" : "Fitting the storyboard"));
  if (producing && phase.changed_since) {
    line.append(el("span", "join-finding warning", "The breakdown changed since the approval"));
  }
  const decide = (command) => async () => {
    const why = prompt(producing ? "Why reopen the storyboard?" : "Approve the storyboard as what will be produced. Why?") ;
    if (why === null) return;
    try {
      await runCommand(command, { scene_id: scene.id, expected_revision: scene.revision, rationale: why,
        actor: { id: "control-room", kind: "human" } });
      await renderScene(scene.id);
    } catch (error) {
      alert(error.message);
    }
  };
  line.append(producing
    ? button("Reopen the storyboard", decide("reopen_storyboard"), "quiet-button")
    : button("Approve the storyboard", decide("approve_storyboard"), "quiet-button"));
  return line;
}

async function renderScene(sceneId, { record = true } = {}) {
  const scene = await api(`/api/scene?id=${encodeURIComponent(sceneId)}`);
  state.currentView = "scene";
  state.sceneId = sceneId;
  state.shotId = null;
  highlight(null);
  if (record) remember({ view: "scene", scene: sceneId });
  const root = byId("workspace");
  root.replaceChildren();

  const back = button("← All scenes", () => setView("scenes"), "back-button");
  const header = el("section", "scene-header");
  const copy = el("div");
  const meta = el("div", "scene-header-meta");
  meta.append(el("span", "scene-id", scene.id), statusPill(scene.status), el("span", "muted", scene.sequence));
  const place = scene.location && state.production?.locations?.[scene.location];
  copy.append(meta, el("h1", "", scene.title), el("p", "hero-logline", scene.summary));
  if (scene.location) {
    // SPEC-0010: the set this scene is shot in, declared once and shared.
    const others = (place?.appearances || []).filter((id) => id !== scene.id);
    copy.append(el("p", "muted location-line", `Set in ${place ? place.label : scene.location}`
      + (others.length ? ` · also ${others.join(", ")}` : "")));
  }
  copy.append(phaseLine(scene));
  const facts = el("div", "scene-facts");
  facts.append(metric(`R${String(scene.iteration).padStart(2, "0")}`, "Current iteration"), metric(`${scene.duration_seconds}s`, "Target duration"), metric(`${scene.progress}%`, "Workflow"));
  header.append(copy, facts);

  const workflowPanel = el("section", "panel wide-panel");
  workflowPanel.append(sectionHeading("PIPELINE", "Scene workflow", "Each gate records what is ready, waiting, or blocked."));
  const workflow = el("div", "workflow-rail");
  scene.workflow.forEach((step, index) => {
    const item = el("article", `workflow-step workflow-${step.status}`);
    item.append(el("span", "workflow-number", String(index + 1).padStart(2, "0")), el("strong", "", step.label), statusPill(step.status));
    if (step.note) item.append(el("small", "", step.note));
    workflow.append(item);
  });
  workflowPanel.append(workflow);

  root.append(back, header);
  if (scene.blockers.length) {
    const blockers = el("section", "blocker-banner");
    blockers.append(el("strong", "", "Blocked"), el("span", "", scene.blockers.join(" · ")));
    root.append(blockers);
  }
  root.append(workflowPanel);

  const continuity = renderContinuity(scene);
  if (continuity) root.append(continuity);

  const columns = el("section", "scene-columns");
  columns.append(renderShots(scene), renderDecisions(scene));
  root.append(columns);

  const runs = renderWorkflows(scene);
  if (runs) root.append(runs);
  // Master pictures come before the blocks that animate them.
  if (scene.shots.some((shot) => shot.derive)) root.append(renderPictures(scene));
  const blocks = renderBlocks(scene);
  if (blocks) root.append(blocks);
  root.append(renderVersions(scene, { onChanged: () => renderScene(sceneId) }));

  const blockout = renderBlockout(scene);
  if (blockout) root.append(blockout);
  root.append(renderBrief(scene));
  root.append(renderIterations(scene));
  state.scene = scene;
  tellAssistant();
}

const BRIEF_SOURCES = {
  authored: "From the scene file",
  screenplay: "From the screenplay",
  derived: "Computed from geometry, movement or the cut",
  missing: "No record fills this yet",
};

function briefSlot(slot) {
  const row = el("div", `brief-slot brief-${slot.source}`);
  const tag = el("span", "brief-tag", slot.tag);
  const badge = el("span", "brief-source", slot.source);
  badge.title = BRIEF_SOURCES[slot.source] || "";
  row.append(tag, el("p", "", slot.text), badge);
  return row;
}

// The brief a generation would receive, derived from the records above
// (plan step 4). Every line says where it came from, and a shot's local take
// can be reviewed against it.
function renderBrief(scene) {
  const panel = el("section", "panel wide-panel brief-panel");
  panel.append(sectionHeading(
    "BRIEF",
    "What a generation would be told",
    "Auteur Script form, derived from the records. Nothing here is written by hand: fix a line by fixing its record.",
  ));
  const body = el("div", "brief-body", "Deriving…");
  panel.append(body);
  api(`/api/brief?scene=${encodeURIComponent(scene.id)}`).then((brief) => {
    body.replaceChildren();
    const legend = el("div", "brief-legend");
    for (const [source, text] of Object.entries(BRIEF_SOURCES)) {
      const item = el("span", `brief-source brief-${source}`, source);
      item.title = text;
      legend.append(item);
    }
    if (brief.missing) legend.append(el("strong", "brief-missing-count", `${brief.missing} missing`));
    body.append(legend);

    const staging = el("div", "brief-block");
    staging.append(el("h3", "", "Staging"));
    brief.staging.forEach((slot) => staging.append(briefSlot(slot)));
    body.append(staging);

    for (const state of brief.states) {
      const block = el("div", "brief-block");
      const shot = scene.shots.find((item) => item.id === state.shot);
      const title = el("h3", "", `S${state.n} · ${state.shot}${state.label ? ` · ${state.label}` : ""}`);
      if (state.duration_seconds) title.append(el("small", "", ` ${state.duration_seconds} s`));
      block.append(title);
      state.slots.forEach((slot) => block.append(briefSlot(slot)));
      const takes = (shot?.takes || []).filter((take) => take.media);
      if (takes.length) block.append(briefReview(scene, state, takes));
      body.append(block);
    }
  }).catch((error) => body.replaceChildren(el("p", "preview-error", error.message)));
  return panel;
}

// Play a shot's local take beside the lines it was meant to show.
function briefReview(scene, state, takes) {
  const box = el("div", "brief-review");
  const picker = el("div", "brief-takes");
  const stage = el("div", "brief-stage");
  const open = (take) => {
    for (const chip of picker.children) chip.classList.toggle("active", chip.dataset.take === take.id);
    const video = el("video");
    video.src = `/media/${take.media}`;
    video.controls = true;
    video.playsInline = true;
    const cues = el("ol", "brief-cues");
    fetch(`/api/brief-review?scene=${encodeURIComponent(scene.id)}&shot=${encodeURIComponent(state.shot)}&take=${encodeURIComponent(take.id)}`)
      .then((response) => response.json())
      .then((review) => {
        for (const cue of review.cues) {
          const item = el("li", "brief-cue");
          item.dataset.start = cue.startTime;
          item.dataset.end = cue.endTime;
          item.append(el("span", "brief-tag", cue.type), el("p", "", cue.selectedText));
          item.addEventListener("click", () => { video.currentTime = cue.startTime * scale(); video.play(); });
          cues.append(item);
        }
        const exported = el("a", "quiet-button", "Review project (JSON)");
        exported.href = `/api/brief-review?scene=${encodeURIComponent(scene.id)}&shot=${encodeURIComponent(state.shot)}&take=${encodeURIComponent(take.id)}`;
        exported.download = `${scene.id}-${state.shot}-${take.id}.review.json`;
        stage.append(exported);
      });
    // Cue times are planned; a take rarely runs exactly the planned length,
    // so the plan is stretched over the take until a review re-times it.
    const scale = () => (video.duration && state.duration_seconds ? video.duration / state.duration_seconds : 1);
    video.addEventListener("timeupdate", () => {
      const planned = video.currentTime / scale();
      for (const item of cues.children) {
        const active = planned >= Number(item.dataset.start) && planned <= Number(item.dataset.end);
        item.classList.toggle("active", active);
      }
    });
    stage.replaceChildren(video, cues);
  };
  for (const take of takes) {
    const chip = button(take.label || take.id, () => open(take), "blockout-chip");
    chip.dataset.take = take.id;
    if (take.selected) chip.classList.add("selected");
    picker.append(chip);
  }
  box.append(el("span", "eyebrow", "REVIEW A TAKE AGAINST THIS STATE"), picker, stage);
  return box;
}

// Continuity problems are read from the scene geometry before anything is
// generated, because they are cheap to fix on paper and expensive to fix in
// finished shots.
function renderContinuity(scene) {
  if (!scene.findings.length) return null;
  const panel = el("section", "panel wide-panel continuity-panel");
  const errors = scene.findings.filter((finding) => finding.severity === "error").length;
  panel.append(
    sectionHeading(
      "CONTINUITY",
      errors ? `${errors} problem${errors === 1 ? "" : "s"} in the coverage` : "Worth a look",
      "Checked against the scene geometry, before generation.",
    ),
  );
  const list = el("div", "finding-list");
  for (const finding of scene.findings) {
    const card = el("article", `finding-card finding-${finding.severity}`);
    card.append(statusPill(finding.severity === "error" ? "blocked" : "proposed"));
    card.append(el("strong", "", label(finding.code)));
    card.append(el("p", "", finding.message));
    if (finding.shots.length) card.append(el("small", "muted", `Shots: ${finding.shots.join(", ")}`));
    const practice = (state.knowledge?.practices || []).find((item) =>
      item.enforced_by.includes(finding.code),
    );
    if (practice) {
      const why = el("details", "finding-why");
      const summary = el("summary", "", `Why this matters — ${practice.title}`);
      why.append(summary, el("p", "", practice.body.split("\n\n")[0]));
      if (practice.cost) why.append(el("small", "muted", `Cost when missed: ${practice.cost}`));
      card.append(why);
    }
    list.append(card);
  }
  panel.append(list);
  return panel;
}

// What the production has learned, and how much of it the software enforces.
// The number that matters is the second one: a rule nobody checks is a rule
// that depends on someone remembering it at the right moment.
function renderKnowledge() {
  const root = byId("workspace");
  root.replaceChildren();
  const knowledge = state.knowledge;
  if (!knowledge) {
    root.append(el("p", "empty-state", "No knowledge records are available for this project."));
    return;
  }
  const report = knowledge.coverage;
  const heading = sectionHeading(
    "KNOWLEDGE",
    "What we know, and what is enforced",
    "A practice with no check behind it still depends on a person remembering.",
  );
  heading.classList.add("page-heading");
  root.append(heading);

  const facts = el("section", "sequence-facts");
  facts.append(
    metric(`${report.percentage}%`, "Practices enforced", `${report.enforced} of ${report.practices}`),
    metric(String(report.unenforced.length), "Depend on a person"),
    metric(`${report.measured_claims}/${report.claims}`, "Provider claims measured"),
  );
  root.append(facts);

  const practicePanel = el("section", "panel wide-panel");
  practicePanel.append(sectionHeading("PRACTICES", "Rules this production learned"));
  for (const practice of knowledge.practices) {
    const card = el("article", `finding-card finding-${practice.enforced ? "ok" : "warning"}`);
    const head = el("div", "take-head");
    head.append(
      statusPill(practice.enforced ? "approved" : "waiting"),
      el("strong", "", practice.title),
      el("small", "muted", practice.domain),
    );
    card.append(head);
    const why = el("details", "finding-why");
    why.append(el("summary", "", practice.enforced
      ? `Checked by ${practice.enforced_by.join(", ")}`
      : "Not checked by anything yet"));
    why.append(el("p", "", practice.body));
    if (practice.cost) why.append(el("small", "muted", `Cost when missed: ${practice.cost}`));
    if (practice.evidence.length) why.append(el("small", "muted", `Evidence: ${practice.evidence.join(", ")}`));
    card.append(why);
    practicePanel.append(card);
  }
  root.append(practicePanel);

  for (const profile of knowledge.providers) {
    const panel = el("section", "panel wide-panel");
    panel.append(
      sectionHeading(
        "PROVIDER",
        `${profile.title}${profile.version ? ` ${profile.version}` : ""}`,
        profile.measured_with || "Measured on this production.",
      ),
    );
    const list = el("div", "finding-list");
    for (const claim of profile.claims) {
      const card = el("article", `finding-card finding-${claim.impact === "high" ? "error" : "warning"}`);
      const head = el("div", "take-head");
      head.append(
        statusPill(claim.status === "measured" ? "approved" : "proposed"),
        el("small", "muted", claim.measured_on || ""),
        el("small", "muted", `impact ${claim.impact}`),
      );
      card.append(head, el("p", "", claim.claim));
      if (claim.workaround) card.append(el("small", "muted", `Do this instead: ${claim.workaround}`));
      if (claim.evidence.length) card.append(el("small", "muted", `Evidence: ${claim.evidence.join(", ")}`));
      list.append(card);
    }
    panel.append(list);
    root.append(panel);
  }
}

function renderBlockout(scene) {
  const geometry = scene.geometry;
  if (!geometry || !geometry.room) return null;
  const panel = el("section", "panel wide-panel");
  panel.append(
    sectionHeading(
      "BLOCKOUT",
      "Where the cameras are",
      "A plan of the set: subjects, marks, camera positions, the line of action, and what moves in each shot.",
    ),
  );
  const motions = scene.shots.map((shot) => shot.motion).filter(Boolean);
  const canvas = el("canvas", "blockout-canvas");
  const detail = el("div", "blockout-detail");
  let activeShot = "";

  const draw = () =>
    drawBlockout(canvas, geometry, { findings: scene.findings, motions, activeShot });

  if (motions.length) {
    // One chip per shot: select it to see where everything is when it starts and ends.
    const chips = el("div", "blockout-shots");
    const select = (shotId) => {
      activeShot = shotId;
      for (const chip of chips.children) chip.classList.toggle("active", chip.dataset.shot === shotId);
      detail.replaceChildren(...(shotId ? describeMotion(scene, shotId) : []));
      showFrames(shotId);
      draw();
    };
    const all = button("All shots", () => select(""), "blockout-chip active");
    all.dataset.shot = "";
    chips.append(all);
    for (const motion of motions) {
      const chip = button(motion.shot_id, () => select(motion.shot_id), "blockout-chip");
      chip.dataset.shot = motion.shot_id;
      if (motion.kind !== "static" || motion.moved_subjects.length) chip.classList.add("moves");
      chips.append(chip);
    }
    panel.append(chips);
  }
  // The 3D storyboard (CT-0049): boards fix composition; the animatic is for checking, never a model's input.
  let boardsInfo = null;
  const storyboard = el("div", "board-bar");
  const loadBoards = async () => {
    boardsInfo = await api(`/api/boards?scene=${encodeURIComponent(scene.id)}`, { optional: true });
    storyboard.replaceChildren(el("strong", "", "3D storyboard"));
    const job = (kind, text, title) => {
      const action = button(text, () => {
        action.disabled = true;
        startJob(kind, { scene: scene.id }).catch((error) => alert(error.message)).finally(() => { action.disabled = false; });
      }, "blockout-chip");
      action.title = title;
      return action;
    };
    storyboard.append(
      job("boards", "Draw boards", "Clay boards of every shot's first frame, from the plan, with depth. A background job; adopt it from Jobs."),
      job("board_animatic", "3D animatic", "The scene through its cameras, to check timing and sides. Never given to a model."),
    );
    if (boardsInfo?.["sheet.png"]) {
      const link = el("a", "blockout-chip", "Board sheet");
      link.href = `/media/${boardsInfo["sheet.png"]}`;
      link.target = "_blank";
      storyboard.append(link);
    }
    if (boardsInfo?.["animatic.mp4"]) {
      const link = el("a", "blockout-chip", "Watch the animatic");
      link.href = `/media/${boardsInfo["animatic.mp4"]}`;
      link.target = "_blank";
      storyboard.append(link);
    }
    if (activeShot) showFrames(activeShot);
  };
  loadBoards().catch(() => {});
  panel.append(storyboard);

  // Beside the plan, what the selected shot's camera sees (CT-0025), and its 3D board.
  const frames = el("div", "blocking-frames");
  const showFrames = (shotId) => {
    frames.replaceChildren();
    const motion = motions.find((item) => item.shot_id === shotId);
    if (!motion || !motion.start.camera) return;
    const board = boardsInfo?.shots?.[shotId];
    for (const [moment, item] of Object.entries(board?.boards || {})) {
      const figure = el("figure", "blocking-frame board-frame");
      const image = el("img");
      image.src = `/media/${item.path}?v=${item.version}`;
      image.alt = `${shotId} 3D board at ${moment}`;
      figure.append(image, el("figcaption", "", `${board.label} · 3D board${moment === "end" ? " · end" : ""}`));
      if (item.stale) figure.append(el("small", "finding warning", "Drawn before the plan last changed: draw the boards again."));
      frames.append(figure);
    }
    const changes = motion.kind !== "static" || motion.moved_subjects.length;
    if (changes) frames.append(previsPlayer(scene, shotId));
    for (const at of changes ? ["start", "end"] : ["start"]) {
      const figure = el("figure", "blocking-frame");
      const image = el("img");
      image.src = `/api/blocking-frame?scene=${encodeURIComponent(scene.id)}&shot=${encodeURIComponent(shotId)}&at=${at}`;
      image.alt = `${shotId} blocking frame at ${at}`;
      figure.append(image, el("figcaption", "", changes ? `${shotId} · ${at}` : `${shotId} · the whole shot`));
      frames.append(figure);
    }
  };
  panel.append(canvas, frames, detail);
  const legend = el("div", "blockout-legend");
  for (const camera of geometry.cameras) {
    const shots = scene.shots.filter((shot) => shot.camera === camera.id).map((shot) => shot.id);
    const item = el("span", "blockout-legend-item");
    item.append(el("b", "", camera.id), el("small", "", camera.label));
    if (shots.length) item.append(el("em", "", shots.join(", ")));
    legend.append(item);
  }
  panel.append(legend);
  // The canvas needs its measured width, so draw once it is in the document.
  requestAnimationFrame(draw);
  return panel;
}

// The shot as a light animatic (CT-0029): blocking frames sampled over its
// duration by the server, played here at the shot's real length.
function previsPlayer(scene, shotId) {
  const figure = el("figure", "blocking-frame previs-player");
  const image = el("img");
  image.alt = `${shotId} previs`;
  const controls = el("div", "previs-controls");
  const play = button("▶", () => toggle(), "blockout-chip");
  const scrub = el("input");
  scrub.type = "range";
  scrub.min = "0";
  scrub.max = "1000";
  scrub.value = "0";
  const clock = el("small", "muted", "");
  const render = button("Render video", () => {
    render.disabled = true;
    startJob("previs", { scene: scene.id, shot: shotId })
      .catch((error) => alert(error.message))
      .finally(() => { render.disabled = false; });
  }, "blockout-chip");
  render.title = "A background job: it keeps running if you leave this page, and you adopt the result when it is ready.";
  controls.append(play, scrub, clock, render);
  figure.append(image, controls, el("figcaption", "", `${shotId} · previs`));

  let data = null;
  let urls = [];
  let playing = false;
  let startedAt = 0;
  let offset = 0;
  const show = (t) => {
    if (!data) return;
    const index = Math.min(urls.length - 1, Math.round(t * (urls.length - 1)));
    image.src = urls[index];
    scrub.value = String(Math.round(t * 1000));
    clock.textContent = `${(t * data.duration_seconds).toFixed(1)} / ${data.duration_seconds} s`;
  };
  const tick = (now) => {
    if (!playing || !figure.isConnected) return;
    const t = Math.min(1, offset + (now - startedAt) / (data.duration_seconds * 1000));
    show(t);
    if (t >= 1) {
      playing = false;
      play.textContent = "▶";
      offset = 0;
      return;
    }
    requestAnimationFrame(tick);
  };
  const toggle = () => {
    if (!data) return;
    playing = !playing;
    play.textContent = playing ? "❚❚" : "▶";
    if (playing) {
      offset = Number(scrub.value) / 1000 >= 1 ? 0 : Number(scrub.value) / 1000;
      startedAt = performance.now();
      requestAnimationFrame(tick);
    }
  };
  scrub.addEventListener("input", () => {
    playing = false;
    play.textContent = "▶";
    show(Number(scrub.value) / 1000);
  });
  api(`/api/previs?scene=${encodeURIComponent(scene.id)}&shot=${encodeURIComponent(shotId)}`).then((result) => {
    data = result;
    urls = result.frames.map((svg) => `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`);
    show(0);
  }).catch((error) => figure.append(el("p", "preview-error", error.message)));
  return figure;
}

function describeMotion(scene, shotId) {
  const shot = scene.shots.find((item) => item.id === shotId);
  const motion = shot?.motion;
  if (!motion) return [];
  const names = Object.fromEntries(scene.geometry.subjects.map((subject) => [subject.id, subject.label]));
  const framed = (list) =>
    list.length ? list.map((item) => `${names[item.subject] || item.subject} ${item.side}`).join(", ") : "nobody";
  const move = motion.kind === "static"
    ? "Static camera"
    : [
        `${motion.kind} ${motion.direction}`.trim(),
        motion.degrees ? `${motion.degrees}°` : "",
        motion.speed,
        motion.rig ? `rig: ${motion.rig}` : "",
      ]
        .filter(Boolean)
        .join(" · ") + (motion.derived ? "" : " (declared)");
  const rows = [
    ["Camera", `${motion.camera_id || "none"} — ${move}`],
    ["Frame at start", framed(motion.start.framed)],
    ["Frame at end", framed(motion.end.framed)],
  ];
  if (motion.moved_subjects.length) {
    rows.push(["Moves", motion.moved_subjects.map((id) => names[id] || id).join(", ")]);
  }
  if (motion.secondary.length) rows.push(["Also", motion.secondary.join(", ")]);
  if (motion.ends_on) rows.push(["Ends on", motion.ends_on]);
  return rows.map(([label, value]) => {
    const row = el("div", "blockout-detail-row");
    row.append(el("span", "", label), el("b", "", value));
    return row;
  });
}

function renderShots(scene) {
  const panel = el("article", "panel");
  panel.append(sectionHeading("SHOTS", `${scene.shots.length} planned shots`, "Open a shot to compare its alternatives."));
  const list = el("div", "shot-list");
  for (const shot of scene.shots) {
    const row = shot.take_count
      ? button("", () => openCompare(scene.id, shot.id), "shot-row shot-row-open")
      : el("div", "shot-row");
    row.dataset.shotId = shot.id;
    const copy = el("span", "shot-copy");
    copy.append(el("b", "", shot.id), el("strong", "", shot.label));
    row.append(
      copy,
      statusPill(shot.status),
      el("span", "take-count", `${shot.take_count} take${shot.take_count === 1 ? "" : "s"}`),
      el("strong", "selected-take", shot.selected_take || "—"),
    );
    list.append(row);
  }
  if (!scene.shots.length) list.append(el("p", "empty-state", "Shots have not been broken down yet."));
  panel.append(list);
  return panel;
}

async function openCompare(sceneId, shotId, { record = true } = {}) {
  const scene = await api(`/api/scene?id=${encodeURIComponent(sceneId)}`);
  const shot = scene.shots.find((item) => item.id === shotId);
  if (!shot) return renderScene(sceneId);
  state.currentView = "compare";
  state.sceneId = sceneId;
  state.shotId = shotId;
  highlight(null);
  if (record) remember({ view: "compare", scene: sceneId, shot: shotId });
  renderCompare(byId("workspace"), scene, shot, {
    onBack: () => renderScene(sceneId),
    onChanged: async () => {
      state.production = await api("/api/production", { optional: true });
      updateChrome();
      await openCompare(sceneId, shotId);
    },
  });
  state.scene = scene;
  tellAssistant();
}

// What the assistant is told the director sees (ADR 0018): the room, the scene,
// the shot, and what in the room waits for a decision.
function assistantSeen() {
  const scene = state.scene && state.scene.id === state.sceneId ? state.scene : null;
  const room = state.currentView === "compare" ? "comparison of a shot's takes"
    : state.currentView === "scene" ? "scene room" : `${state.currentView} room`;
  const details = [];
  if (scene && state.currentView === "scene") {
    for (const gate of Object.values(scene.gates || {})) {
      if (gate.state === "waiting") {
        details.push(`The gate ${gate.id} is open on screen: approve the picture of ${gate.subject} among ${gate.candidates.length} candidate(s)`);
      }
    }
    for (const run of scene.runs || []) {
      if (!["done", "failed", "cancelled"].includes(run.state)) details.push(`Workflow ${run.id} for block ${run.subject.block}: ${run.state}`);
    }
  }
  if (scene && state.currentView === "compare") {
    const shot = scene.shots.find((item) => item.id === state.shotId);
    if (shot) details.push(`Comparing ${shot.id}'s takes: ${shot.takes.map((take) => `${take.id}${take.selected ? " (chosen)" : ""}`).join(", ")}`);
  }
  return {
    room,
    scene: scene ? scene.id : "",
    focus: scene ? `${scene.id} ${scene.title}` : room,
    selected: state.currentView === "compare" && state.shotId ? `shot ${state.shotId}` : "",
    details: details.join("\n"),
  };
}

// Where the assistant asks to take the screen; it only moves the view.
function assistantNavigate(where) {
  if (!where) return;
  if (where.room === "canvas") window.location.href = "/app/";
  else if (where.room === "editor") window.location.href = "/app/script.html";
  else if (where.room === "scene" && where.scene) renderScene(where.scene);
  else if (where.room === "compare" && where.scene && where.shot) {
    openCompare(where.scene, /^P/i.test(where.shot) ? where.shot : `P${where.shot}`);
  } else if (ROOMS.has(where.room)) setView(where.room);
}

function renderDecisions(scene) {
  const panel = el("article", "panel");
  panel.append(sectionHeading("DECISIONS", "Creative memory", "Open questions stay attached to the scene."));
  const list = el("div", "decision-list");
  for (const decision of scene.decisions) {
    const card = el("article", "decision-card");
    card.append(statusPill(decision.status), el("strong", "", decision.question));
    if (decision.answer) card.append(el("p", "", decision.answer));
    list.append(card);
  }
  if (!scene.decisions.length) list.append(el("p", "empty-state", "No recorded decisions."));
  panel.append(list);
  return panel;
}

function renderIterations(scene) {
  const panel = el("section", "panel wide-panel");
  panel.append(sectionHeading("ITERATIONS", "What changed and why", "Previous rounds remain legible instead of becoming mystery folders."));
  const timeline = el("div", "iteration-timeline");
  for (const iteration of scene.iterations) {
    const card = el("article", "iteration-card");
    card.append(el("strong", "", iteration.id), statusPill(iteration.result), el("p", "", iteration.note));
    timeline.append(card);
  }
  if (!scene.iterations.length) timeline.append(el("p", "empty-state", "This scene has no completed iteration yet."));
  panel.append(timeline);
  return panel;
}

function renderReview() {
  if (!state.production) return renderUnstructured();
  const root = byId("workspace");
  root.replaceChildren();
  const reviewScenes = state.production.scenes.filter((scene) => scene.status === "in_review" || scene.shots.some((shot) => shot.status === "needs_review"));
  const heading = sectionHeading("REVIEW ROOM", "Awaiting a creative decision", "Review is a gate in the production, not a folder full of outputs.");
  heading.classList.add("page-heading");
  root.append(heading);
  for (const scene of reviewScenes) {
    const panel = el("section", "review-scene panel");
    const panelHeading = sectionHeading(scene.id, scene.title, `${scene.sequence} · iteration ${scene.iteration}`);
    panelHeading.append(button("Open scene →", () => renderScene(scene.id)));
    panel.append(panelHeading);
    const cards = el("div", "review-grid");
    for (const shot of scene.shots.filter((entry) => entry.status === "needs_review")) {
      const card = el("article", "review-card");
      const visual = el("div", "review-placeholder");
      visual.append(el("span", "", shot.id), el("strong", "", `${shot.take_count} candidates`));
      card.append(
        visual,
        el("strong", "", shot.label),
        el("small", "", "No take selected"),
        button("Compare candidates", () => openCompare(scene.id, shot.id), "primary-button"),
      );
      cards.append(card);
    }
    panel.append(cards);
    root.append(panel);
  }
  if (!reviewScenes.length) root.append(el("p", "empty-state", "The review queue is empty."));
}

function demoTexture(gl, variant) {
  const surface = document.createElement("canvas");
  surface.width = 640;
  surface.height = 360;
  const context = surface.getContext("2d");
  const gradient = context.createLinearGradient(0, 0, 640, 360);
  if (variant === "from") {
    gradient.addColorStop(0, "#162d42");
    gradient.addColorStop(1, "#d45b35");
  } else {
    gradient.addColorStop(0, "#d4aa52");
    gradient.addColorStop(1, "#244f3d");
  }
  context.fillStyle = gradient;
  context.fillRect(0, 0, 640, 360);
  context.fillStyle = "rgba(255,255,255,.12)";
  context.beginPath();
  context.arc(variant === "from" ? 175 : 465, 180, 110, 0, Math.PI * 2);
  context.fill();
  context.fillStyle = "rgba(255,255,255,.92)";
  context.font = "800 92px system-ui";
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.fillText(variant === "from" ? "A" : "B", variant === "from" ? 175 : 465, 180);
  context.font = "600 18px system-ui";
  context.fillText(variant === "from" ? "OUTGOING SHOT" : "INCOMING SHOT", 320, 320);

  const texture = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, texture);
  gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, surface);
  return texture;
}

function compileShader(gl, type, source) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    throw new Error(gl.getShaderInfoLog(shader) || "Shader compilation failed");
  }
  return shader;
}

function setShaderParam(gl, program, { name, type, default: value }) {
  const location = gl.getUniformLocation(program, name);
  if (!location) return;
  const values = Array.isArray(value) ? value : [Number(value)];
  const setters = {
    float: "uniform1fv", vec2: "uniform2fv", vec3: "uniform3fv", vec4: "uniform4fv",
    int: "uniform1iv", bool: "uniform1iv", ivec2: "uniform2iv", ivec3: "uniform3iv", ivec4: "uniform4iv",
  };
  const setter = setters[type];
  if (!setter) return;
  const typed = setter.endsWith("iv") ? new Int32Array(values) : new Float32Array(values);
  gl[setter](location, typed);
}

async function startShaderPreview(canvas, transition) {
  const gl = canvas.getContext("webgl", { alpha: false, antialias: true });
  if (!gl) {
    canvas.replaceWith(el("p", "preview-error", "WebGL is unavailable."));
    return;
  }
  try {
    const shaderCode = await fetch(transition.asset_url).then((response) => response.text());
    const vertexSource = `
      attribute vec2 position;
      varying vec2 vUv;
      void main() {
        vUv = position * 0.5 + 0.5;
        gl_Position = vec4(position, 0.0, 1.0);
      }
    `;
    const fragmentSource = `
      #ifdef GL_FRAGMENT_PRECISION_HIGH
      precision highp float;
      #else
      precision mediump float;
      #endif
      uniform sampler2D fromTexture;
      uniform sampler2D toTexture;
      uniform float progress;
      uniform float ratio;
      varying vec2 vUv;
      vec4 getFromColor(vec2 uv) { return texture2D(fromTexture, uv); }
      vec4 getToColor(vec2 uv) { return texture2D(toTexture, uv); }
      ${shaderCode}
      void main() { gl_FragColor = transition(vUv); }
    `;
    const program = gl.createProgram();
    gl.attachShader(program, compileShader(gl, gl.VERTEX_SHADER, vertexSource));
    gl.attachShader(program, compileShader(gl, gl.FRAGMENT_SHADER, fragmentSource));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
    gl.useProgram(program);

    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]), gl.STATIC_DRAW);
    const position = gl.getAttribLocation(program, "position");
    gl.enableVertexAttribArray(position);
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);

    const fromTexture = demoTexture(gl, "from");
    const toTexture = demoTexture(gl, "to");
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, fromTexture);
    gl.uniform1i(gl.getUniformLocation(program, "fromTexture"), 0);
    gl.activeTexture(gl.TEXTURE1);
    gl.bindTexture(gl.TEXTURE_2D, toTexture);
    gl.uniform1i(gl.getUniformLocation(program, "toTexture"), 1);
    gl.uniform1f(gl.getUniformLocation(program, "ratio"), canvas.width / canvas.height);
    // The shader's own parameters, at the defaults it declares: an unset
    // uniform is zero, and many transitions do nothing at zero.
    for (const param of transition.params || []) setShaderParam(gl, program, param);
    const progressLocation = gl.getUniformLocation(program, "progress");
    const started = performance.now();
    const duration = Math.max(250, transition.duration_ms);

    function draw(now) {
      if (!canvas.isConnected) return;
      const cycle = duration + 1000;
      const elapsed = (now - started) % cycle;
      const progress = Math.max(0, Math.min(1, (elapsed - 350) / duration));
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.uniform1f(progressLocation, progress);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
      requestAnimationFrame(draw);
    }
    requestAnimationFrame(draw);
  } catch (error) {
    const message = el("p", "preview-error", `Shader error: ${error.message}`);
    canvas.replaceWith(message);
  }
}

function transitionVisual(transition, large = false, lazy = false) {
  const frame = el("div", large ? "transition-visual transition-visual-large" : "transition-visual");
  if (lazy && transition.kind === "glsl") {
    // A browser keeps only a few WebGL contexts alive, so a bank of a hundred
    // shaders plays one at a time, while the pointer is on it.
    frame.classList.add("transition-visual-lazy");
    frame.append(el("span", "lazy-hint", "Hover to play"));
    let canvas = null;
    frame.addEventListener("pointerenter", () => {
      canvas = el("canvas");
      canvas.width = 640;
      canvas.height = 360;
      frame.prepend(canvas);
      startShaderPreview(canvas, transition);
    });
    frame.addEventListener("pointerleave", () => {
      if (!canvas) return;
      canvas.getContext("webgl")?.getExtension("WEBGL_lose_context")?.loseContext();
      canvas.remove();
      canvas = null;
    });
  } else if (transition.kind === "webm") {
    const video = el("video");
    video.src = transition.preview_url;
    video.muted = true;
    video.loop = true;
    video.autoplay = true;
    video.playsInline = true;
    video.controls = large;
    frame.append(video);
  } else {
    const canvas = el("canvas");
    canvas.width = large ? 960 : 640;
    canvas.height = large ? 540 : 360;
    frame.append(canvas);
    startShaderPreview(canvas, transition);
  }
  const badge = el("span", "format-badge", transition.kind.toUpperCase());
  frame.append(badge);
  return frame;
}

// The camera-move catalog (CT-0027): what each move says, when to use it, the
// geometry it implies (checked against the plan), and the words a model gets.
// The sets (SPEC-0010): each declared once, with its plan, its plates, and
// the scenes shot there. A location is edited in its location.yaml; this
// room shows what the runtime reads from it.
async function renderLocations() {
  const root = byId("workspace");
  root.replaceChildren();
  const heading = sectionHeading("LOCATIONS", "Locations",
    "Each set declared once: its room, marks, cameras, set pieces and plates. Scenes set there take its plan and add who is in it.");
  heading.classList.add("page-heading");
  root.append(heading);
  const locations = (await api("/api/locations", { optional: true })) || [];
  if (!locations.length) {
    root.append(el("p", "empty-state", "No location yet. Declare one in locations/<id>/location.yaml, or pin one from the backlot (toast backlot pin)."));
    tellAssistant();
    return;
  }
  for (const location of locations) {
    const panel = el("section", "panel wide-panel location-panel");
    panel.append(sectionHeading(location.id, location.label, location.description || ""));
    const body = el("div", "location-body");
    const plan = el("div", "location-plan");
    if (location.plan?.room) {
      const canvas = el("canvas", "blockout-canvas");
      plan.append(canvas);
      requestAnimationFrame(() => drawBlockout(canvas, { subjects: [], axis: null, ...location.plan }));
    } else {
      plan.append(el("p", "empty-state", location.plan?.error || "No room declared: nothing to draw."));
    }
    const facts = el("div", "location-facts");
    const room = location.plan?.room;
    if (room) facts.append(el("p", "", `Room ${room.width} × ${room.depth} m, ${room.height} m high.`));
    const list = (title, items, describe) => {
      if (!items?.length) return;
      const block = el("div", "location-list");
      block.append(el("strong", "", title));
      const ul = el("ul");
      for (const item of items) ul.append(el("li", "", describe(item)));
      block.append(ul);
      facts.append(block);
    };
    list("Cameras", location.plan?.cameras, (camera) =>
      `${camera.id} · ${camera.lens_mm} mm · ${camera.height != null ? `${camera.height} m high` : "height not set"}${camera.label && camera.label !== camera.id ? ` · ${camera.label}` : ""}`);
    list("Marks", location.plan?.marks, (mark) => `${mark.id}${mark.label && mark.label !== mark.id ? ` · ${mark.label}` : ""}`);
    list("Set pieces", location.plan?.set_pieces, (piece) => `${piece.label} · ${piece.width} × ${piece.depth} × ${piece.height} m`);
    const scenes = el("div", "location-list");
    scenes.append(el("strong", "", "Scenes shot here"));
    if (location.appearances?.length) {
      const links = el("div", "location-scenes");
      for (const sceneId of location.appearances) links.append(button(sceneId, () => renderScene(sceneId), "quiet-button"));
      scenes.append(links);
    } else {
      scenes.append(el("small", "muted", "None yet: a scene names it with location: " + location.id));
    }
    facts.append(scenes);
    if (location.pinned) {
      const state_ = location.backlot || {};
      const notes = [`Pinned from the backlot ${String(location.pinned.pinned_at || "").slice(0, 10)}`];
      if (state_.edited_here) notes.push("edited here since");
      if (state_.backlot_moved_on) notes.push("the backlot has a newer version (toast backlot pin --update)");
      if (location.backlot && !state_.in_backlot) notes.push("no longer in the backlot");
      facts.append(el("small", state_.backlot_moved_on ? "finding warning" : "muted", notes.join(" · ")));
    }
    body.append(plan, facts);
    panel.append(body);
    const plates = (location.references || []).filter((ref) => ref.kind === "plate");
    if (plates.length) {
      const strip = el("div", "location-plates");
      for (const plate of plates) {
        const figure = el("figure", "location-plate");
        if (plate.exists) {
          const image = el("img");
          image.src = `/media/${plate.path}`;
          image.alt = `Plate from ${plate.camera}`;
          image.loading = "lazy";
          figure.append(image);
        } else {
          figure.append(el("div", "empty-state", "missing"));
        }
        figure.append(el("figcaption", "", `Plate from ${plate.camera || "—"} · a picture can be made from it: derive: {from: location:${plate.camera}}`));
        strip.append(figure);
      }
      panel.append(strip);
    } else {
      panel.append(el("small", "muted", "No plates yet: photograph or render the empty set from a camera and list it under references (kind: plate, camera: <id>)."));
    }
    root.append(panel);
  }
  tellAssistant();
}

// A move played on a fixed stage (a person, a column, a cabinet), from the
// same blocking frames a shot's previs uses. Fetched when first wanted, played
// while the pointer rests on it.
function movePreview(move) {
  const box = el("div", "move-preview");
  box.append(el("span", "muted", "Preview"));
  let frames = null;
  let timer = null;
  let note = "";
  const show = (index) => { box.innerHTML = frames[index]; if (note) box.append(el("small", "move-note", note)); };
  const play = async () => {
    if (timer) return;
    if (!frames) {
      const answer = await api(`/api/camera-move-preview?id=${encodeURIComponent(move.id)}`, { optional: true });
      if (!answer) return;
      ({ frames, note } = answer);
      show(0);
    }
    let index = 0;
    timer = setInterval(() => {
      index = (index + 1) % (frames.length + 6);  // a short hold on the last frame
      show(Math.min(index, frames.length - 1));
    }, 1000 / 12);
  };
  const stop = () => { clearInterval(timer); timer = null; if (frames) show(0); };
  box.addEventListener("mouseenter", play);
  box.addEventListener("mouseleave", stop);
  box.addEventListener("focus", play);
  box.addEventListener("blur", stop);
  box.tabIndex = 0;
  box.title = "Rest the pointer here to play the move";
  return box;
}

// The title catalog (CT-0031): each item previewed by its own engine, with
// the text the director types. A shot names one with title: {id: …, text: …}.
async function renderTitles() {
  const root = byId("workspace");
  root.replaceChildren();
  const heading = sectionHeading("TITLES", "Titles",
    "Title effects chosen like transitions: a shot names one with title: {id: …, text: …}. The preview is drawn by the item's own engine.");
  heading.classList.add("page-heading");
  root.append(heading);
  state.titles ??= (await api("/api/titles", { optional: true })) || [];
  const tryText = el("input", "title-try");
  tryText.placeholder = "Try your own text (Enter)";
  tryText.maxLength = 80;
  root.append(tryText);
  const cards = [];
  const categories = new Map();
  for (const item of state.titles) {
    if (!categories.has(item.category)) categories.set(item.category, []);
    categories.get(item.category).push(item);
  }
  for (const [category, items] of categories) {
    const section = el("section", "transition-section");
    section.append(sectionHeading("TITLES", label(category), `${items.length} available`));
    const grid = el("div", "transition-grid");
    for (const item of items) {
      const card = el("article", "transition-card move-card");
      const picture = el("div", "move-preview title-preview");
      const image = el("img");
      image.alt = item.name;
      image.loading = "lazy";
      image.addEventListener("error", () => picture.replaceChildren(el("small", "move-note", "The preview could not be drawn.")));
      const load = () => {
        const text = tryText.value.trim();
        image.src = `/api/title-preview?id=${encodeURIComponent(item.id)}${text ? `&text=${encodeURIComponent(text)}` : ""}`;
      };
      if (item.unavailable) picture.append(el("small", "move-note", item.unavailable));
      else { picture.append(image); load(); }
      cards.push(load);
      const engine = item.engine === "blender" ? "Blender (3D)" : "FFmpeg";
      card.append(
        picture,
        el("strong", "", item.name),
        el("code", "move-id", `title: {id: ${item.id}, text: …}`),
        el("p", "", item.says),
        el("small", "muted", `${engine} · ${item.effect} · energy ${item.energy || "—"}${item.origin !== "built-in" ? ` · ${item.origin}` : ""}`),
        guidanceList("Use when", item.use_when, "good"),
        guidanceList("Avoid when", item.avoid_when, "warning"),
      );
      grid.append(card);
    }
    section.append(grid);
    root.append(section);
  }
  tryText.addEventListener("keydown", (event) => { if (event.key === "Enter") cards.forEach((load) => load()); });
  tellAssistant();
}

// The VFX catalog (CT-0031): procedural effects drawn by FFmpeg, and
// composites of the production's own stock elements. A shot lists them:
// effects: [{id: …}, …], applied in order before its title.
async function renderVfx() {
  const root = byId("workspace");
  root.replaceChildren();
  const heading = sectionHeading("VFX", "Visual effects",
    "Effects chosen like titles: a shot lists them with effects: [{id: …}]. Element effects composite stock elements the production brings (vfx_elements/<id>/element.toml).");
  heading.classList.add("page-heading");
  root.append(heading);
  state.vfx = (await api("/api/vfx", { optional: true })) || { effects: [], elements: [] };
  const byCategory = new Map();
  for (const item of state.vfx.effects) {
    if (!byCategory.has(item.category)) byCategory.set(item.category, []);
    byCategory.get(item.category).push(item);
  }
  for (const [category, items] of byCategory) {
    const section = el("section", "transition-section");
    section.append(sectionHeading("VFX", label(category), `${items.length} available`));
    const grid = el("div", "transition-grid");
    for (const item of items) {
      const card = el("article", "transition-card move-card");
      const box = el("div", "move-preview vfx-preview");
      const needs = item.element_category;
      const have = state.vfx.elements.filter((element) => element.category === needs && element.exists);
      if (needs && !have.length) {
        box.append(el("small", "move-note", `No ${needs} element yet: bring one to vfx_elements/`));
      } else {
        box.append(el("span", "muted", "Preview"));
        let video = null;
        box.addEventListener("mouseenter", () => {
          if (!video) {
            video = el("video");
            Object.assign(video, { muted: true, loop: true, playsInline: true, src: `/api/vfx-preview?id=${encodeURIComponent(item.id)}` });
            video.addEventListener("error", () => box.replaceChildren(el("small", "move-note", "The preview could not be drawn.")));
            box.replaceChildren(video);
          }
          video.play().catch(() => {});
        });
        box.addEventListener("mouseleave", () => video?.pause());
      }
      card.append(
        box,
        el("strong", "", item.name),
        el("code", "move-id", needs ? `effects: [{id: ${item.id}, element: …}]` : `effects: [{id: ${item.id}}]`),
        el("p", "", item.says),
        el("small", "muted", `${needs ? `composites a ${needs} element` : `FFmpeg · ${item.effect}`} · energy ${item.energy || "—"}${item.origin !== "built-in" ? ` · ${item.origin}` : ""}`),
        guidanceList("Use when", item.use_when, "good"),
        guidanceList("Avoid when", item.avoid_when, "warning"),
      );
      grid.append(card);
    }
    section.append(grid);
    root.append(section);
  }
  const library = el("section", "panel wide-panel");
  library.append(sectionHeading("ELEMENTS", "The production's stock elements",
    "Packs you are licensed for (ActionVFX, FootageCrate, your own renders), each with its blend: screen or add for black-backed, alpha, or key for green."));
  if (!state.vfx.elements.length) library.append(el("p", "empty-state", "None yet."));
  for (const element of state.vfx.elements) {
    library.append(el("p", "", `${element.id} · ${element.category} · ${element.blend}${element.exists ? "" : " · file missing"}${element.source ? ` · from ${element.source}` : ""}${element.license ? ` · ${element.license}` : ""}`));
  }
  root.append(library);
  tellAssistant();
}

// The sound catalog (CT-0048): ambiences, effects, Foley and music, heard at
// their level. A shot places sounds: [{id: …, at: …}]; a scene names its
// ambience and music. Recordings come from Freesound, Sonniss or Openverse
// (toast sound search/fetch) with their licence; generated ones are ours.
async function renderSounds() {
  const root = byId("workspace");
  root.replaceChildren();
  const heading = sectionHeading("SOUND", "Sound",
    "Placed like effects: a shot lists sounds: [{id: …, at: 1.2}]; a scene names ambience: … and music: {id: …, from: P2}. Music is lowered under speech. Fetch recordings with toast sound search/fetch (Freesound CC0, Sonniss, Openverse).");
  heading.classList.add("page-heading");
  root.append(heading);
  state.sounds = (await api("/api/sounds", { optional: true })) || [];
  const byCategory = new Map();
  for (const item of state.sounds) {
    if (!byCategory.has(item.category)) byCategory.set(item.category, []);
    byCategory.get(item.category).push(item);
  }
  const placing = { ambience: (id) => `ambience: ${id}`, music: (id) => `music: {id: ${id}, from: …}` };
  for (const [category, items] of byCategory) {
    const section = el("section", "transition-section");
    section.append(sectionHeading("SOUND", label(category), `${items.length} available`));
    const grid = el("div", "transition-grid");
    for (const item of items) {
      const card = el("article", "transition-card move-card");
      const box = el("div", "sound-preview");
      if (!item.exists) {
        box.append(el("small", "move-note", "Its file is missing."));
      } else {
        const play = el("button", "secondary-button", "Listen");
        play.type = "button";
        play.addEventListener("click", () => {
          const audio = el("audio");
          Object.assign(audio, { controls: true, autoplay: true, src: `/api/sound-preview?id=${encodeURIComponent(item.id)}` });
          audio.addEventListener("error", () => box.replaceChildren(el("small", "move-note", "The preview could not be made.")));
          box.replaceChildren(audio);
        });
        box.append(play);
      }
      const where = (placing[category] || ((id) => `sounds: [{id: ${id}, at: …}]`))(item.id);
      const status = item.status ? ` · ${item.status}` : "";
      card.append(
        el("strong", "", item.name),
        el("code", "move-id", where),
        el("p", "", item.says),
        box,
        el("small", "muted", `${item.generated ? "generated, ours" : `${item.provenance || "a recording"} · ${item.licence || "licence not stated"}`}${status} · ${item.params.level} LUFS${item.origin !== "built-in" ? ` · ${item.origin}` : ""}`),
        guidanceList("Use when", item.use_when, "good"),
      );
      if (item.credit) card.append(el("small", "muted", `Credit: ${item.credit}`));
      if (item.status === "provisional") card.append(el("small", "warning", "Provisional: replace with the official file before release."));
      grid.append(card);
    }
    section.append(grid);
    root.append(section);
  }
  tellAssistant();
}

async function renderMoves() {
  const root = byId("workspace");
  root.replaceChildren();
  const heading = sectionHeading("CAMERA MOVES", "Camera moves",
    "A shared vocabulary of moves. A shot names one with move: {id: …}; the plan checks it, and generation tells the model in its words.");
  heading.classList.add("page-heading");
  root.append(heading);
  state.moves ??= (await api("/api/camera-moves", { optional: true })) || [];
  const categories = new Map();
  for (const move of state.moves) {
    if (!categories.has(move.category)) categories.set(move.category, []);
    categories.get(move.category).push(move);
  }
  for (const [category, moves] of categories) {
    const section = el("section", "transition-section");
    section.append(sectionHeading("MOVES", label(category), `${moves.length} available`));
    const grid = el("div", "transition-grid");
    for (const move of moves) {
      const card = el("article", "transition-card move-card");
      const implied = move.implies;
      const geometry = implied.kind
        ? [`${implied.kind} ${implied.direction}`.trim(), implied.rig, implied.speed, ...(implied.secondary || [])].filter(Boolean).join(" · ")
        : `rig: ${implied.rig || "any"} (the plan cannot see it)`;
      card.append(
        movePreview(move),
        el("strong", "", move.name),
        el("code", "move-id", `move: {id: ${move.id}}`),
        el("p", "", move.says),
        el("small", "muted", `Plan: ${geometry} · energy ${move.energy || "—"}${move.origin !== "built-in" ? ` · ${move.origin}` : ""}`),
        guidanceList("Use when", move.use_when, "good"),
        guidanceList("Avoid when", move.avoid_when, "warning"),
        el("small", "move-prompt", `Model: “${move.prompt}”`),
      );
      grid.append(card);
    }
    section.append(grid);
    root.append(section);
  }
  tellAssistant();
}

function renderTransitions() {
  const root = byId("workspace");
  root.replaceChildren();
  const heading = sectionHeading("TRANSITION BANK", "Transitions", "Preview a shared visual vocabulary and expose the same intent to production agents.");
  heading.classList.add("page-heading");
  root.append(heading);

  const reviewed = state.transitions.filter((transition) => transition.curated !== false);
  const unreviewed = state.transitions.filter((transition) => transition.curated === false);
  const categories = new Map();
  for (const transition of reviewed) {
    if (!categories.has(transition.category)) categories.set(transition.category, []);
    categories.get(transition.category).push(transition);
  }
  for (const [category, transitions] of categories) {
    const section = el("section", "transition-section");
    section.append(sectionHeading("BANK", label(category), `${transitions.length} available`));
    const grid = el("div", "transition-grid");
    transitions.forEach((transition) => grid.append(transitionCard(transition)));
    section.append(grid);
    root.append(section);
  }

  if (unreviewed.length) {
    const section = el("details", "transition-section transition-unreviewed");
    const summary = el("summary");
    summary.append(sectionHeading(
      "NOT REVIEWED · GL-TRANSITIONS",
      `${unreviewed.length} more shaders`,
      "Usable and rendered by their own shader, but nobody has said when they serve a film. Reviewing one gives it a manifest and moves it up.",
    ));
    section.append(summary);
    const grid = el("div", "transition-grid");
    unreviewed.forEach((transition) => grid.append(transitionCard(transition, true)));
    section.append(grid);
    root.append(section);
  }
}

function transitionCard(transition, lazy = false) {
  const card = el("article", "transition-card");
  card.append(transitionVisual(transition, false, lazy));
  const copy = el("div", "transition-card-copy");
  const top = el("div", "transition-card-top");
  top.append(el("strong", "", transition.name));
  if (transition.curated === false) top.append(el("span", "energy energy-unknown", "unreviewed"));
  else top.append(el("span", `energy energy-${transition.energy}`, transition.energy));
  copy.append(top, el("p", "", transition.curated === false ? `by ${transition.author || "unknown"} · ${transition.license}` : transition.description));
  const tags = el("div", "tag-list");
  transition.tags.slice(0, 4).forEach((tag) => tags.append(el("span", "tag", tag)));
  copy.append(tags, button(transition.curated === false ? "Inspect" : "Inspect and guide AI", () => renderTransitionDetail(transition.id), "quiet-button"));
  card.append(copy);
  return card;
}

function guidanceList(title, values, tone) {
  const panel = el("article", `guidance-list guidance-${tone}`);
  panel.append(el("span", "eyebrow", title));
  const list = el("ul");
  values.forEach((value) => list.append(el("li", "", value)));
  panel.append(list);
  return panel;
}

function renderTransitionDetail(transitionId) {
  const transition = state.transitions.find((item) => item.id === transitionId);
  if (!transition) return;
  state.currentView = "transition";
  const root = byId("workspace");
  root.replaceChildren();
  const back = button("← Transition bank", () => setView("transitions"), "back-button");
  const header = el("section", "transition-detail-header");
  const copy = el("div");
  const meta = el("div", "scene-header-meta");
  meta.append(el("span", "scene-id", transition.kind.toUpperCase()), el("span", "status", label(transition.category)), el("span", "muted", `${transition.duration_ms} ms`));
  copy.append(meta, el("h1", "", transition.name), el("p", "hero-logline", transition.description));
  header.append(copy);
  root.append(back, header, transitionVisual(transition, true));

  const aiPanel = el("section", "panel ai-guidance-panel");
  const aiHeading = sectionHeading("AGENT GUIDANCE", "How the AI should reason about it", "This text is part of the catalog, not inferred from the filename.");
  aiPanel.append(aiHeading, el("blockquote", "", transition.guidance || "Not reviewed. Nothing tells an agent when this serves a film, so it should not propose it."));
  const facts = el("dl", "transition-facts");
  const rows = [["Energy", transition.energy], ["Motion", transition.motion], ["Asset role", transition.webm_role], ["Origin", transition.origin], ["License", transition.license]];
  if (transition.author) rows.push(["Author", transition.author]);
  rows.push(["Film render", transition.render?.ffmpeg ? `shader, or FFmpeg ${transition.render.ffmpeg} without GL` : "shader only (needs GL)"]);
  for (const [name, value] of rows) {
    facts.append(el("dt", "", name), el("dd", "", name === "Author" || name === "Film render" ? value : label(value)));
  }
  if (transition.source) {
    const link = el("a", "", "source");
    link.href = transition.source;
    link.target = "_blank";
    link.rel = "noopener";
    const dd = el("dd");
    dd.append(link);
    facts.append(el("dt", "", "Source"), dd);
  }
  aiPanel.append(facts);
  if ((transition.params || []).length) {
    const params = el("dl", "transition-facts transition-params");
    for (const param of transition.params) {
      const value = Array.isArray(param.default) ? param.default.join(", ") : String(param.default);
      params.append(el("dt", "", param.name), el("dd", "", `${param.type} = ${value}`));
    }
    aiPanel.append(el("span", "eyebrow", "SHADER PARAMETERS (DEFAULTS)"), params);
  }
  const guidance = el("div", "guidance-columns");
  guidance.append(guidanceList("USE WHEN", transition.use_when, "use"), guidanceList("AVOID WHEN", transition.avoid_when, "avoid"));
  root.append(aiPanel, guidance);
}

function renderUnstructured() {
  const root = byId("workspace");
  root.replaceChildren();
  const panel = el("section", "unstructured panel");
  panel.append(
    el("span", "eyebrow", "UNSTRUCTURED DIRECTORY"),
    el("h1", "", state.project.name),
    el("p", "", "This directory can be inspected as a library, but it has no Cine Toaster operational manifest. No project files will be changed."),
    button("Open library", () => setView("library"), "primary-button"),
  );
  root.append(panel);
}


// ---- Writing: what is this scene? -------------------------------------------

async function writing() {
  if (!state.writing) state.writing = await api("/api/writing", { optional: true });
  return state.writing;
}

function emptyRoom(root, title, explanation) {
  const panel = el("section", "panel");
  panel.append(sectionHeading("NOTHING HERE YET", title, explanation));
  root.append(panel);
}

async function renderScript() {
  const root = byId("workspace");
  root.replaceChildren();
  const data = await writing();
  if (!data) return renderUnstructured();

  const header = el("section", "scene-header");
  const copy = el("div");
  copy.append(
    el("span", "eyebrow", "SCRIPT"),
    el("h1", "", data.title),
    el("p", "hero-logline", data.logline || ""),
  );
  const facts = el("div", "scene-facts");
  facts.append(
    metric(String(data.counts.scenes), "Scenes"),
    metric(String(data.counts.lines), "Spoken lines"),
    metric(String(data.counts.open_questions), "Open questions"),
  );
  header.append(copy, facts);
  root.append(header);

  for (const scene of data.scenes) {
    if (!scene.script || !scene.script.linked) continue;
    root.append(renderCoverage(scene));
  }

  if (data.screenplay) {
    const panel = el("section", "panel wide-panel");
    const files = data.script_files || [];
    panel.append(sectionHeading(
      "SCREENPLAY",
      data.script_path,
      files.length > 1 ? `${files.length} authored files, read in order as one screenplay.` : "The authored file, as written.",
    ));
    const edit = el("a", "quiet-button screenplay-edit", "Open in the screenplay editor");
    edit.href = "/app/script.html";
    const page = el("pre", "screenplay-page");
    page.textContent = data.screenplay;
    panel.append(edit, page);
    root.append(panel);
  } else {
    emptyRoom(
      root,
      "This production has no screenplay file",
      "Point `paths.script` at one in project.yaml, or add a .fountain file. " +
        "The scene direction below is what the production says instead.",
    );
  }

  const scenes = el("section", "panel wide-panel");
  scenes.append(sectionHeading("DIRECTION", "What each scene is", "Scene summaries and the direction written for them."));
  const list = el("div", "script-scenes");
  for (const scene of data.scenes) {
    const card = el("article", "script-scene");
    const head = el("div", "script-scene-head");
    head.append(el("span", "scene-id", scene.id), el("strong", "", scene.title));
    if (scene.sequence) head.append(el("span", "muted", scene.sequence));
    card.append(head);
    if (scene.summary) card.append(el("p", "", scene.summary));
    if (scene.direction) {
      const direction = el("blockquote", "scene-direction");
      direction.textContent = scene.direction;
      card.append(direction);
    }
    for (const question of scene.open_questions) {
      card.append(el("p", "open-question", `Open: ${question.question}`));
    }
    card.append(button("Open scene →", () => renderScene(scene.id), "quiet-button"));
    list.append(card);
  }
  scenes.append(list);
  root.append(scenes);
}

async function renderStoryboard() {
  const root = byId("workspace");
  root.replaceChildren();
  const data = await writing();
  if (!data) return renderUnstructured();

  const header = el("section", "scene-header");
  const copy = el("div");
  copy.append(el("span", "eyebrow", "STORYBOARD"), el("h1", "", "Every frame, in order"));
  const facts = el("div", "scene-facts");
  facts.append(
    metric(String(data.counts.frames), "Frames"),
    metric(String(data.counts.stills), "Drawn"),
    metric(String(data.counts.scenes), "Scenes"),
  );
  header.append(copy, facts);
  root.append(header);

  if (!data.counts.stills) {
    emptyRoom(
      root,
      "No frames have been drawn yet",
      "Composed shots get their still from `toast build`; generated shots get " +
        "theirs from a take. Until then a scene is text on a screen.",
    );
  }

  for (const scene of data.scenes) {
    const panel = el("section", "panel wide-panel");
    panel.append(sectionHeading(scene.id, scene.title, scene.summary || ""));
    const strip = el("div", "filmstrip");
    for (const frame of scene.frames) {
      const card = el("article", "filmstrip-card");
      const frameBox = el("div", "filmstrip-frame");
      if (frame.still) {
        const image = el("img");
        image.src = `/media/${frame.still}`;
        image.alt = frame.label;
        image.loading = "lazy";
        frameBox.append(image);
      } else {
        frameBox.append(el("span", "filmstrip-blank", frame.take_count ? "take" : "not drawn"));
      }
      card.append(frameBox);
      const meta = el("div", "filmstrip-meta");
      meta.append(el("strong", "", frame.shot_id), el("span", "muted", `${frame.duration_seconds}s`));
      card.append(meta, el("p", "", frame.label));
      card.append(frameScript(frame));
      if (frame.transition) {
        card.append(el("small", "filmstrip-transition", `↳ ${frame.transition.id}`));
      }
      card.addEventListener("click", () => renderScene(scene.id));
      strip.append(card);
    }
    panel.append(strip);
    root.append(panel);
  }
}

// A linked scene's screenplay, formatted, with the shots that cover each unit in
// the margin. A speech no shot covers is marked: it is a line nobody films.
function renderCoverage(scene) {
  const panel = el("section", "panel wide-panel");
  const where = scene.script.occurrence > 1 ? ` (occurrence ${scene.script.occurrence})` : "";
  panel.append(
    sectionHeading(scene.id, `${scene.title} — coverage`, `${scene.script.heading}${where}`),
  );
  const page = el("div", "coverage-page");
  for (const unit of scene.script.units) {
    const row = el("div", `coverage-row coverage-${unit.kind}`);
    const margin = el("div", "coverage-margin");
    for (const shotId of unit.shots) {
      margin.append(button(shotId, () => renderScene(scene.id), "coverage-chip"));
    }
    const body = el("div", "coverage-body");
    if (unit.kind === "speech") {
      body.append(el("div", "coverage-speaker", unit.speaker + (unit.extension ? ` (${unit.extension})` : "") + (unit.dual ? " ^" : "")));
      for (const part of unit.parts) {
        body.append(el("div", part.kind === "parenthetical" ? "coverage-paren" : "coverage-dialogue", part.kind === "parenthetical" ? `(${part.text})` : part.text));
      }
      if (!unit.shots.length) {
        row.classList.add("uncovered");
        margin.append(el("span", "coverage-missing", "no shot"));
      }
    } else {
      body.append(el("div", "", unit.text));
    }
    row.append(margin, body);
    page.append(row);
  }
  panel.append(page);
  return panel;
}

// What a storyboard frame holds of the screenplay (SPEC-0006), in screenplay order.
function frameScript(frame) {
  const box = el("div", "frame-script");
  const script = frame.script;
  if (!script) {
    box.append(el("small", "muted", "not linked to the screenplay"));
    return box;
  }
  const units = script.units.filter((unit) => unit.kind !== "heading");
  if (!units.length) {
    box.append(el("small", "muted", "covers no screenplay"));
    return box;
  }
  const delivery = Object.fromEntries(
    script.dialogue.filter((line) => line.delivery).map((line) => [line.unit, line.delivery]),
  );
  for (const unit of units) {
    if (unit.kind === "speech") {
      const line = el("p", "frame-line");
      const who = unit.speaker + (unit.extension ? ` (${unit.extension})` : "");
      line.append(el("b", "", who), document.createTextNode(` ${unit.text}`));
      if (delivery[unit.index]) line.append(el("em", "", ` — ${delivery[unit.index]}`));
      box.append(line);
    } else {
      box.append(el("p", "frame-action", unit.text));
    }
  }
  return box;
}

async function renderDialogue() {
  const root = byId("workspace");
  root.replaceChildren();
  const data = await writing();
  if (!data) return renderUnstructured();

  const header = el("section", "scene-header");
  const copy = el("div");
  copy.append(el("span", "eyebrow", "DIALOGUE"), el("h1", "", "Who says what"));
  const facts = el("div", "scene-facts");
  facts.append(
    metric(String(data.counts.lines), "Lines"),
    metric(String(data.counts.speakers), "Speakers"),
  );
  header.append(copy, facts);
  root.append(header);

  if (!data.counts.lines) {
    emptyRoom(
      root,
      "Nobody speaks in this production yet",
      "A shot carries `lines`, each with who says it, how, and where it sits in the mix.",
    );
    return;
  }

  const castPanel = el("section", "panel");
  castPanel.append(sectionHeading("CAST", "Voices in this production", "Counted from the lines themselves."));
  const castList = el("div", "cast-list");
  for (const member of data.cast) {
    const card = el("article", "cast-card");
    card.append(
      el("strong", "", member.who),
      el("span", "muted", `${member.lines} line(s) · ${member.scenes.join(", ")}`),
    );
    castList.append(card);
  }
  castPanel.append(castList);
  root.append(castPanel);

  for (const scene of data.scenes) {
    if (!scene.lines.length) continue;
    const panel = el("section", "panel wide-panel");
    panel.append(sectionHeading(scene.id, scene.title, ""));
    const sheet = el("div", "dialogue-sheet");
    for (const line of scene.lines) {
      const entry = el("article", "dialogue-line");
      entry.append(el("strong", "dialogue-who", line.who || "—"));
      if (line.delivery) entry.append(el("em", "dialogue-delivery", `(${line.delivery})`));
      entry.append(el("p", "dialogue-text", line.text || line.en || ""));
      if (line.en && line.text && line.en !== line.text) {
        entry.append(el("p", "dialogue-alt", line.en));
      }
      const meta = [];
      if (line.voice) meta.push(line.voice);
      if (line.mix && line.mix.file) meta.push(line.mix.file);
      if (meta.length) entry.append(el("small", "muted", meta.join(" · ")));
      sheet.append(entry);
    }
    panel.append(sheet);
    root.append(panel);
  }
}

// ---- Production: is this good? ----------------------------------------------

// Generation blocks (CT-0037): shots made together in one generation, and the
// clip that came back. Slicing finds where the model really cut and turns each
// stretch into a take of its shot, kept beside the others.
// The built-in workflow (SPEC-0009): picture, a person's approval, video,
// takes. It moves by itself between gates; at a gate it waits here, and the
// decision is a production record like choosing a take.
const STEP_STATES = { done: "approved", skipped: "approved", running: "in_progress", waiting: "needs_review",
  failed: "blocked", pending: "planned" };

function renderWorkflows(scene) {
  const blocks = (scene.blocks || []).filter((block) => block.contiguous);
  const generated = scene.shots.some((shot) => shot.source === "generated" && !shot.block);
  if (!blocks.length && !generated && !(scene.runs || []).length) return null;
  const panel = el("section", "panel wide-panel");
  panel.append(sectionHeading(
    "WORKFLOW",
    "From picture to takes",
    "Each run makes the master pictures a block needs, stops for a person to approve them, then generates the block and slices it into takes. Paid steps run within the budget.",
  ));
  const act = async (command, payload) => {
    try {
      await runCommand(command, { scene_id: scene.id, expected_revision: scene.revision,
        actor: { id: "control-room", kind: "human" }, ...payload });
      await renderScene(scene.id);
    } catch (error) {
      alert(error.message);
    }
  };
  const active = new Set((scene.runs || []).filter((run) => !["done", "failed", "cancelled"].includes(run.state))
    .map((run) => run.subject.block).filter(Boolean));
  const starts = el("div", "take-actions");
  for (const block of blocks) {
    if (active.has(block.id)) continue;
    starts.append(button(`Start for block ${block.id} (${block.shots.join(", ")})`,
      () => act("start_workflow", { block: block.id }), "quiet-button"));
  }
  // A generated shot outside any block has a workflow of its own, ending in a take.
  const busyShots = new Set((scene.runs || []).filter((run) => !["done", "failed", "cancelled"].includes(run.state))
    .map((run) => run.subject.shot).filter(Boolean));
  const loose = scene.shots.filter((shot) => shot.source === "generated" && !shot.block && !busyShots.has(shot.id));
  if (loose.length) {
    const picker = el("select", "take-picker");
    for (const shot of loose) {
      const option = el("option", "", `${shot.id} · ${shot.label}`);
      option.value = shot.id;
      picker.append(option);
    }
    starts.append(picker, button("Start for this shot", () => act("start_workflow", { shot: picker.value }), "quiet-button"));
  }
  if (starts.childElementCount) panel.append(starts);
  for (const run of scene.runs || []) panel.append(workflowRun(scene, run, act));
  return panel;
}

function workflowRun(scene, run, act) {
  const box = el("article", "workflow-run");
  const head = el("div", "block-head");
  head.append(el("strong", "", run.subject.shot ? `Shot ${run.subject.shot}` : `Block ${run.subject.block}`),
    el("span", `status status-${STEP_STATES[run.state] || "planned"}`, label(run.state)),
    el("span", "muted", `${run.id} · ${run.created_at.slice(0, 16).replace("T", " ")}`));
  box.append(head);
  const rail = el("div", "workflow-rail");
  run.steps.forEach((step, index) => {
    const item = el("article", `workflow-step workflow-${STEP_STATES[step.state] || step.state}`);
    item.append(el("span", "workflow-number", String(index + 1).padStart(2, "0")), el("strong", "", step.label),
      el("small", "", step.state));
    const detail = step.note || (step.outputs || []).map((value) => value.split("/").pop()).join(", ");
    if (detail) item.append(el("small", "muted", detail));
    rail.append(item);
  });
  box.append(rail);
  const waiting = run.steps.find((step) => step.state === "waiting" && step.gate);
  if (waiting && scene.gates[waiting.gate]) box.append(gateCard(scene, scene.gates[waiting.gate], act));
  if (!["done", "failed", "cancelled"].includes(run.state)) {
    const actions = el("div", "take-actions");
    actions.append(button("Cancel run", () => {
      if (confirm("Cancel this run? Its running job is stopped; what it made is kept.")) {
        act("cancel_workflow", { workflow_id: run.id });
      }
    }, "quiet-button"));
    box.append(actions);
  }
  return box;
}

// A waiting gate: every candidate side by side, each with what it was made from.
function gateCard(scene, gate, act) {
  const card = el("div", "gate-card");
  const shot = scene.shots.find((item) => item.id === gate.subject);
  card.append(el("h4", "", `Approve the picture for ${shot ? shot.number : gate.subject}`),
    el("p", "muted", "The approved version becomes the picture the block is animated from. Look at where people are against the render: the edge score cannot tell."));
  const why = el("textarea", "gate-why");
  why.placeholder = "Why — optional to approve; required to ask for another or to reject: say what is wrong";
  // What is wrong, from a fixed list, so refusals can be counted later.
  const REASONS = { subject_moved: "Subject moved", identity: "Wrong face", geometry: "Geometry",
    light: "Light", detail_lost: "Detail lost", anatomy: "Anatomy", other: "Other" };
  const reasons = el("div", "gate-reasons");
  for (const [value, text] of Object.entries(REASONS)) {
    const item = el("label", "gate-reason");
    const box = el("input");
    box.type = "checkbox";
    box.value = value;
    item.append(box, document.createTextNode(` ${text}`));
    reasons.append(item);
  }
  const chosenReasons = () => [...reasons.querySelectorAll("input:checked")].map((box) => box.value);
  const grid = el("div", "gate-candidates");
  card.append(grid);
  api(`/api/pictures?scene=${encodeURIComponent(scene.id)}`).then((pictures) => {
    const records = Object.fromEntries(pictures.flatMap((picture) => picture.versions.map((v) => [v.path, v.record])));
    const source = (pictures.find((picture) => picture.shot === gate.subject) || {}).source;
    if (source) {
      const figure = el("figure", "sent-picture");
      const image = el("img");
      image.src = `/media/${source}`;
      figure.append(image, el("figcaption", "", "Source (the render)"));
      grid.append(figure);
    }
    for (const path of gate.candidates) {
      const figure = el("figure", "sent-picture");
      const image = el("img");
      image.src = `/media/${path}`;
      const details = sentDetails(records[path]);
      figure.append(image, el("figcaption", "", path.split("/").pop()));
      if (details) figure.append(details);
      figure.append(button("Approve this", () => act("decide_gate",
        { gate_id: gate.id, outcome: "approved", chosen: path, rationale: why.value }), "primary-button"));
      grid.append(figure);
    }
  }).catch((error) => grid.append(el("p", "join-finding warning", error.message)));
  const refuse = (outcome) => {
    if (!why.value.trim() && !chosenReasons().length) {
      why.focus();
      alert("Say what is wrong: tick a reason or write one. It is what the next version has to fix.");
      return;
    }
    act("decide_gate", { gate_id: gate.id, outcome, rationale: why.value, reasons: chosenReasons() });
  };
  const actions = el("div", "take-actions");
  actions.append(
    button("Ask for another version", () => refuse("changes_requested"), "quiet-button"),
    button("Reject (end the run)", () => refuse("rejected"), "quiet-button"),
  );
  card.append(el("strong", "", "What is wrong?"), reasons, why, actions);
  return card;
}

// Master pictures made by editing a source -- a render of the 3D set -- with
// the cast's faces. Every edit is a version beside the picture; each shows
// what it was made from, and a new one is sent from the view of what it
// would be given.
function renderPictures(scene) {
  const panel = el("section", "panel wide-panel");
  panel.append(sectionHeading(
    "PICTURES",
    "Master pictures",
    "Each is an edit of its source with the cast's faces. Versions are kept; nothing replaces the picture in use.",
  ));
  const list = el("div", "block-list");
  panel.append(list);
  api(`/api/pictures?scene=${encodeURIComponent(scene.id)}`).then((pictures) => {
    for (const picture of pictures) list.append(pictureCard(scene, picture));
  }).catch((error) => list.append(el("p", "join-finding warning", error.message)));
  return panel;
}

function pictureCard(scene, picture) {
  const card = el("article", "block-card");
  const head = el("div", "block-head");
  head.append(el("strong", "", picture.number), el("span", "muted", picture.label));
  card.append(head);
  const versions = picture.versions;
  const image = el("img", "picture-version");
  const sent = el("div", "block-sent");
  let chosen = versions[0];
  const show = (version) => {
    chosen = version;
    image.src = `/media/${version ? version.path : picture.source}`;
    const details = version ? sentDetails(version.record, `What ${version.path.split("/").pop()} was made from`) : null;
    sent.replaceChildren(...(details ? [details] : []));
  };
  card.append(image);
  if (!versions.length) card.append(el("p", "muted", `No picture yet; its source is ${picture.source || "missing"}.`));
  if (versions.length > 1) {
    const row = el("div", "block-versions");
    for (const version of versions) {
      const name = version.path.split("/").pop().replace(/\.[^.]+$/, "");
      const pick = button(name, () => {
        show(version);
        row.querySelectorAll("button").forEach((item) => item.classList.toggle("active", item === pick));
      }, `quiet-button ${version === chosen ? "active" : ""}`);
      row.append(pick);
    }
    card.append(row);
  }
  show(chosen);
  const planned = el("div", "block-plan");
  const open = button("What would be sent…", async () => {
    open.disabled = true;
    try {
      const query = new URLSearchParams({ scene: scene.id, shot: picture.shot });
      const plan = await api(`/api/picture-plan?${query}`);
      const view = el("div", "sent-plan");
      view.append(el("h4", "", `${picture.number}: what the editor would be given`), sentView(plan, { plan: true }));
      const actions = el("div", "take-actions");
      const send = button(plan.limit_usd ? `Send (≈ US$ ${plan.estimate_usd.toFixed(2)})` : "Send (no budget set)", async () => {
        send.disabled = true;
        try {
          await startJob("derive_picture", { scene: scene.id, shot: picture.shot });
          planned.replaceChildren(el("p", "muted", "Sent. Progress is in the jobs tray; adopt the result to see it here."));
        } catch (error) {
          alert(error.message);
          send.disabled = false;
        }
      }, "primary-button");
      send.disabled = !plan.limit_usd;
      actions.append(send, button("Close", () => planned.replaceChildren()));
      view.append(actions);
      planned.replaceChildren(view);
    } catch (error) {
      planned.replaceChildren(el("p", "join-finding warning", error.message));
    } finally {
      open.disabled = false;
    }
  }, "quiet-button");
  card.append(sent, open, planned);
  return card;
}

function renderBlocks(scene) {
  const blocks = scene.blocks || [];
  if (!blocks.length) return null;
  const panel = el("section", "panel wide-panel");
  panel.append(sectionHeading(
    "BLOCKS",
    "Shots generated together",
    "Each block is one generation. Slicing its clip gives every shot a new take, cut where the model really cut.",
  ));
  const list = el("div", "block-list");
  for (const block of blocks) {
    const card = el("article", `block-card ${block.contiguous ? "" : "warning"}`);
    const head = el("div", "block-head");
    head.append(el("strong", "", `Block ${block.id}`), el("span", "muted", `${block.shots.join(" · ")} · ${block.duration}s`));
    card.append(head);
    const planned = el("div", "block-plan");
    if (block.clip) {
      const video = el("video");
      video.src = `/media/${block.clip}`;
      video.controls = true;
      video.preload = "metadata";
      card.append(video);
      // Every generation of the block is kept; the one shown is the one sliced,
      // and what it was made from is shown beneath it.
      const versions = block.versions || [block.clip];
      let chosen = block.clip;
      const sent = el("div", "block-sent");
      const showSent = () => {
        const details = sentDetails((block.records || {})[chosen], `What ${chosen.split("/").pop()} was made from`);
        sent.replaceChildren(...(details ? [details] : []));
      };
      if (versions.length > 1) {
        const row = el("div", "block-versions");
        for (const path of versions) {
          const name = path.split("/").pop();
          const pick = button(name.replace(/\.[^.]+$/, ""), () => {
            chosen = path;
            video.src = `/media/${path}`;
            row.querySelectorAll("button").forEach((item) => item.classList.toggle("active", item === pick));
            showSent();
          }, `quiet-button ${path === chosen ? "active" : ""}`);
          row.append(pick);
        }
        card.append(row);
      }
      showSent();
      card.append(sent);
      const slice = button("Slice into takes", async () => {
        slice.disabled = true;
        try {
          const params = { scene: scene.id, block: block.id };
          if (chosen !== block.clip) params.clip = chosen.split("/").pop();
          await startJob("slice_block", params);
        } catch (error) {
          alert(error.message);
        } finally {
          slice.disabled = false;
        }
      }, "quiet-button");
      card.append(slice);
    } else {
      card.append(el("p", "muted", `No clip yet (b${block.id}.mp4 in the scene's work folder).`));
    }
    if (block.contiguous) card.append(generateButton(scene, block, planned), planned);
    if (!block.contiguous) card.append(el("p", "join-finding warning", "These shots are not consecutive in the cut."));
    list.append(card);
  }
  panel.append(list);
  return panel;
}

// A paid generation of the block. Everything the model will be given is shown
// first -- pictures, the frames they guide, the prompt by shot, the estimate
// against the budget -- and nothing is sent until it is confirmed there.
function generateButton(scene, block, holder) {
  const start = button("What would be sent…", async () => {
    start.disabled = true;
    try {
      const query = new URLSearchParams({ scene: scene.id, block: block.id });
      const plan = await api(`/api/generation-plan?${query}`);
      const view = el("div", "sent-plan");
      view.append(el("h4", "", `Block ${plan.block}: what the model would be given`), sentView(plan, { plan: true }));
      const actions = el("div", "take-actions");
      const send = button(plan.limit_usd ? `Send (≈ US$ ${plan.estimate_usd.toFixed(2)})` : "Send (no budget set)", async () => {
        send.disabled = true;
        try {
          await startJob("generate_block", { scene: scene.id, block: block.id });
          holder.replaceChildren(el("p", "muted", "Sent. Progress is in the jobs tray; adopt the result to see it here."));
        } catch (error) {
          alert(error.message);
          send.disabled = false;
        }
      }, "primary-button");
      send.disabled = !plan.limit_usd;
      actions.append(send, button("Close", () => holder.replaceChildren()));
      if (!plan.limit_usd) view.append(el("p", "join-finding warning", "No generation budget is set: toast budget set <usd>."));
      view.append(actions);
      holder.replaceChildren(view);
    } catch (error) {
      holder.replaceChildren(el("p", "join-finding warning", error.message));
    } finally {
      start.disabled = false;
    }
  }, "quiet-button");
  return start;
}

const CUT_NAMES = {
  hard: "Hard cut", match: "Match cut", action: "Cut on action", j: "J-cut",
  l: "L-cut", smash: "Smash cut", jump: "Jump cut", continuation: "Continuation",
};

function renderJoins(scene) {
  const panel = el("section", "panel wide-panel");
  panel.append(sectionHeading(`JOINS · ${scene.id}`, scene.title, "How each shot becomes the next, and what the join has to hold."));
  const names = Object.fromEntries((scene.geometry?.subjects || []).map((s) => [s.id, s.label]));
  const shots = Object.fromEntries(scene.shots.map((shot) => [shot.id, shot]));
  const framing = (state) =>
    state.framed.length ? state.framed.map((f) => `${names[f.subject] || f.subject} ${f.side}`).join(", ") : "nobody";
  const line = (unit) =>
    !unit ? "—" : unit.kind === "speech" ? `${unit.speaker}: ${unit.text}` : unit.text;

  const list = el("div", "join-list");
  for (const cut of scene.cuts) {
    const card = el("article", "join-card");
    if (cut.findings.some((f) => f.severity === "error")) card.classList.add("error");
    else if (cut.findings.some((f) => f.severity === "warning")) card.classList.add("warning");

    const top = el("div", "join-top");
    const side = (shotId) => {
      const shot = shots[shotId];
      const box = el("div", "join-shot");
      const frame = el("div", "join-frame");
      if (shot?.still) {
        const image = el("img");
        image.src = `/media/${shot.still}`;
        image.alt = shot.label;
        frame.append(image);
      } else {
        frame.append(el("span", "muted", shotId));
      }
      box.append(frame, el("strong", "", shotId), el("small", "muted", shot?.label || ""));
      return box;
    };
    const middle = el("div", "join-type");
    middle.append(el("b", "", CUT_NAMES[cut.type] || cut.type));
    if (cut.chain) middle.append(el("small", "", "frames chained"));
    if (cut.transition?.id) middle.append(el("small", "", `↳ ${cut.transition.id}`));
    if (cut.type === "j" || cut.type === "l") {
      const seconds = cut.split || 0.8;
      middle.append(el("small", "", cut.type === "j" ? `sound leads ${seconds} s` : `sound runs on ${seconds} s`));
    }
    top.append(side(cut.from), middle, side(cut.to));
    card.append(top);

    const rows = [
      ["Leaves", framing(cut.exit)],
      ["Finds", framing(cut.entry)],
      ["Last line out", line(cut.exit.unit)],
      ["First line in", line(cut.entry.unit)],
    ];
    if (cut.exit.ends_on) rows.push(["Ends on", cut.exit.ends_on]);
    if (cut.reason) rows.push(["Why", cut.reason]);
    for (const [label, value] of rows) {
      const row = el("div", "join-row");
      row.append(el("span", "", label), el("b", "", value));
      card.append(row);
    }
    for (const finding of cut.findings) {
      card.append(el("p", `join-finding ${finding.severity}`, `${finding.code}: ${finding.message}`));
    }
    list.append(card);
  }
  panel.append(list);
  return panel;
}

async function renderCut() {
  const root = byId("workspace");
  root.replaceChildren();
  const production = state.production;
  if (!production) return renderUnstructured();

  const header = el("section", "scene-header");
  const copy = el("div");
  copy.append(el("span", "eyebrow", "CUT"), el("h1", "", "What has been assembled"));
  const facts = el("div", "scene-facts");
  facts.append(
    metric(String((production.renders || []).length), "Renders"),
    metric(String(production.sequences.length), "Sequences"),
  );
  header.append(copy, facts);
  root.append(header);

  // Every join between adjacent shots, scene by scene (SPEC-0007).
  for (const scene of production.scenes) {
    if (scene.cuts && scene.cuts.length) root.append(renderJoins(scene));
  }

  const renders = production.renders || [];
  if (!renders.length) {
    emptyRoom(
      root,
      "Nothing has been assembled yet",
      "`toast build` writes into the production's renders/ directory. Anything " +
        "found there appears here; nothing has to be declared.",
    );
  }

  for (const render of renders) {
    const panel = el("section", "panel wide-panel");
    panel.append(sectionHeading("ASSEMBLED", render.name, render.path));
    const video = el("video");
    video.src = `/media/${render.path}`;
    video.controls = true;
    video.preload = "metadata";
    panel.append(video);
    panel.append(el("small", "muted", `${Math.round(render.size_bytes / 1024)} KB`));
    root.append(panel);
  }

  for (const sequence of production.sequences) {
    if (!sequence.render) continue;
    const panel = el("section", "panel wide-panel");
    panel.append(sectionHeading("SEQUENCE", sequence.label, sequence.render));
    const video = el("video");
    video.src = `/media/${sequence.render}`;
    video.controls = true;
    video.preload = "metadata";
    panel.append(video);
    root.append(panel);
  }
}

function humanSize(bytes) {
  let value = Number(bytes || 0);
  for (const unit of ["B", "KiB", "MiB", "GiB", "TiB"]) {
    if (value < 1024 || unit === "TiB") return unit === "B" ? `${value} B` : `${value.toFixed(1)} ${unit}`;
    value /= 1024;
  }
}

function mediaUrl(item) {
  return `/media/${item.relative_path.split("/").map(encodeURIComponent).join("/")}`;
}

function createPreview(item) {
  const container = el("div", "media-preview");
  const url = mediaUrl(item);
  if (item.media_type === "image") {
    const image = el("img"); image.src = url; image.alt = item.name; container.append(image);
  } else if (item.media_type === "video") {
    const video = el("video"); video.src = url; video.controls = true; video.preload = "metadata"; container.append(video);
  } else if (item.media_type === "audio") {
    const audio = el("audio"); audio.src = url; audio.controls = true; container.append(audio);
  } else if (item.extension === ".pdf") {
    const frame = el("iframe"); frame.src = url; frame.title = item.name; container.append(frame);
  } else if (item.media_type === "text") {
    const pre = el("pre", "", "Loading…");
    fetch(url).then((response) => response.text()).then((text) => { pre.textContent = text; });
    container.append(pre);
  } else container.append(el("p", "empty-state", "Preview unavailable."));
  return container;
}

async function openItem(item) {
  if (item.is_directory) return renderLibrary(item.id);
  byId("preview-kind").textContent = label(item.kind);
  byId("preview-name").textContent = item.name;
  byId("preview-path").textContent = `${item.relative_path} · ${humanSize(item.size)}`;
  byId("preview-content").replaceChildren(createPreview(item));
  byId("preview-dialog").showModal();
}

async function renderLibrary(itemId) {
  state.currentView = "library";
  state.libraryPath = itemId;
  document.querySelectorAll("[data-view]").forEach((node) => node.classList.toggle("active", node.dataset.view === "library"));
  const [item, children] = await Promise.all([
    api(`/api/item?id=${encodeURIComponent(itemId)}`),
    api(`/api/items?parent=${encodeURIComponent(itemId)}`),
  ]);
  const root = byId("workspace");
  root.replaceChildren();
  const breadcrumbs = el("nav", "breadcrumbs");
  item.ancestors.forEach((ancestor, index) => {
    if (index) breadcrumbs.append(" / ");
    breadcrumbs.append(button(ancestor.name, () => renderLibrary(ancestor.id), "breadcrumb-button"));
  });
  const heading = sectionHeading("PROJECT LIBRARY", item.name, `${children.length} items · files are supporting material, not the production model.`);
  heading.classList.add("page-heading");
  const grid = el("section", "library-grid");
  for (const child of children) {
    const card = button("", () => openItem(child), "library-card");
    const icon = child.is_directory ? "DIR" : child.media_type === "video" ? "▶" : child.media_type === "image" ? "IMG" : child.media_type === "audio" ? "AUD" : "DOC";
    card.append(el("span", "library-icon", icon), el("small", "", label(child.kind)), el("strong", "", child.name));
    grid.append(card);
  }
  root.append(breadcrumbs, heading, grid);
}

async function runSearch(query) {
  const results = await api(`/api/search?q=${encodeURIComponent(query)}`);
  const root = byId("search-results");
  root.replaceChildren();
  for (const result of results) {
    const row = button("", () => openItem(result), "search-result");
    row.append(el("strong", "", result.name), el("span", "", result.relative_path));
    if (result.snippet) row.append(el("small", "", result.snippet));
    root.append(row);
  }
  if (!results.length) root.append(el("p", "empty-state", "No matches."));
}

function updateChrome() {
  byId("project-name").textContent = state.production?.title || state.project.name;
  byId("project-root").textContent = state.project.root;
  byId("project-format").textContent = state.production?.format || "UNSTRUCTURED";
  byId("project-phase").textContent = label(state.production?.production?.current_phase || "Library only");
  byId("scene-nav-count").textContent = state.production?.metrics.total_scenes || 0;
  byId("sequence-nav-count").textContent = state.production?.metrics.total_sequences || 0;
  byId("knowledge-nav-count").textContent = state.knowledge?.coverage.practices || 0;
  byId("review-nav-count").textContent = state.production?.metrics.pending_shots ?? state.production?.metrics.attention_items ?? 0;
  byId("transition-nav-count").textContent = state.transitions.length;
  const castCount = byId("cast-nav-count");
  if (castCount) castCount.textContent = String(Object.keys(state.production?.cast || {}).length);
  const locationCount = byId("locations-nav-count");
  if (locationCount) locationCount.textContent = String(Object.keys(state.production?.locations || {}).length);
  byId("cut-nav-count").textContent = (state.production?.renders || []).length;
  const writingCounts = state.writing?.counts;
  byId("storyboard-nav-count").textContent = writingCounts?.frames ?? 0;
  byId("dialogue-nav-count").textContent = writingCounts?.lines ?? 0;
}

// A decision committed from the CLI, an agent, or a second window is the same
// event as one made here, so the open interface follows it instead of going
// stale.
async function refreshFromEvent(event) {
  state.events = [event, ...state.events].slice(0, 40);
  state.production = await api("/api/production", { optional: true });
  updateChrome();
  if (state.currentView === "compare" && state.sceneId && state.shotId) {
    await openCompare(state.sceneId, state.shotId);
  } else if (state.currentView === "scene" && state.sceneId) {
    await renderScene(state.sceneId);
  } else if (state.currentView === "overview") {
    renderOverview();
  } else if (state.currentView === "review") {
    renderReview();
  } else if (state.currentView === "sequences") {
    renderSequences();
  }
}

const JOB_LABELS = {
  queued: "Queued", running: "Running", succeeded: "Ready", failed: "Failed",
  cancelled: "Cancelled", interrupted: "Interrupted",
};

async function jobAction(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error?.message || `Request failed (${response.status})`);
  return payload;
}

async function startJob(kind, params) {
  const job = await jobAction("/api/jobs", { kind, params });
  await renderJobs(true);
  return job;
}

// Background work this runtime holds for the production (SPEC-0008). It
// lives outside the page: reloading or leaving the room does not stop it.
async function renderJobs(open = false) {
  let tray = byId("jobs-tray");
  if (!tray) {
    tray = el("aside", "jobs-tray");
    tray.id = "jobs-tray";
    document.body.append(tray);
  }
  const jobs = (await api("/api/jobs", { optional: true })) || [];
  const recent = jobs.filter((job) => !job.adopted_at || ["queued", "running"].includes(job.state)).slice(0, 6);
  tray.replaceChildren();
  tray.hidden = !recent.length;
  if (!recent.length) return;
  const active = recent.filter((job) => ["queued", "running"].includes(job.state)).length;
  const details = el("details");
  details.open = open || tray.dataset.open === "true" || active > 0;
  details.addEventListener("toggle", () => { tray.dataset.open = String(details.open); });
  details.append(el("summary", "", active ? `Jobs · ${active} running` : `Jobs · ${recent.length} ready`));
  for (const job of recent) {
    const row = el("div", `job-row job-${job.state}`);
    const title = Object.values(job.params || {}).join(" ");
    row.append(el("strong", "", `${job.kind} ${title}`), el("span", "job-state", JOB_LABELS[job.state] || job.state));
    const bar = el("div", "job-bar");
    const fill = el("span");
    fill.style.width = `${Math.round((job.progress || 0) * 100)}%`;
    bar.append(fill);
    row.append(bar, el("small", "muted", job.error || job.message || ""));
    const actions = el("div", "job-actions");
    const act = (text, path, body) => button(text, () => jobAction(path, body).then(() => renderJobs(true)).catch((error) => alert(error.message)), "blockout-chip");
    if (["queued", "running"].includes(job.state)) actions.append(act("Cancel", `/api/jobs/${job.id}/cancel`));
    if (job.state === "succeeded" && !job.adopted_at) {
      const destination = (job.result?.files || []).map((file) => file.destination).join(", ");
      const adopt = button(`Adopt → ${destination}`, async () => {
        try {
          await jobAction(`/api/jobs/${job.id}/adopt`);
        } catch (error) {
          // Adoption never replaces a file silently: the person decides.
          if (!error.message.includes("exists") || !confirm(`${error.message}\n\nReplace it?`)) {
            if (!error.message.includes("exists")) alert(error.message);
            return;
          }
          await jobAction(`/api/jobs/${job.id}/adopt`, { overwrite: true }).catch((again) => alert(again.message));
        }
        renderJobs(true);
        // Adoption changed the production (a new render, perhaps a new
        // version): refresh now rather than waiting for the event stream.
        refreshFromEvent({ type: "job.adopted" }).catch(() => {});
      }, "blockout-chip");
      actions.append(adopt);
    }
    if (["failed", "cancelled", "interrupted"].includes(job.state)) actions.append(act("Retry", `/api/jobs/${job.id}/retry`));
    row.append(actions);
    details.append(row);
  }
  tray.append(details);
  // Progress arrives as events at most once a second; poll gently as a fallback.
  clearTimeout(renderJobs.timer);
  if (active) renderJobs.timer = setTimeout(() => renderJobs().catch(() => {}), 1500);
}

function startEventStream() {
  const source = new EventSource("/api/events/stream");
  source.addEventListener("message", (message) => {
    let event;
    try {
      event = JSON.parse(message.data);
    } catch {
      return;
    }
    // Job events move the tray only; a page re-render every second would
    // restart videos and players. Adoption changed the production, so it
    // refreshes like any committed change.
    if (event.type && event.type.startsWith("job.")) {
      renderJobs().catch(() => {});
      if (event.type !== "job.adopted") return;
    }
    refreshFromEvent(event).catch(() => {});
  });
  source.addEventListener("error", () => {
    // EventSource reconnects on its own; the stream is capped server-side so a
    // long session reconnects periodically by design.
  });
}

async function start() {
  [state.project, state.production, state.transitions, state.events] = await Promise.all([
    api("/api/project"),
    api("/api/production", { optional: true }),
    api("/api/transitions"),
    api("/api/events?limit=25", { optional: true }).then((value) => (value || []).reverse()),
  ]);
  state.knowledge = await api("/api/knowledge", { optional: true });
  updateChrome();
  startEventStream();
  renderJobs().catch(() => {});
  startAssistant({ seen: assistantSeen, navigate: assistantNavigate }).catch(() => {});
  api("/api/vfx", { optional: true }).then((vfx) => {
    state.vfx = vfx || { effects: [], elements: [] };
    const count = byId("vfx-nav-count");
    if (count) count.textContent = String(state.vfx.effects.length);
  }).catch(() => {});
  api("/api/sounds", { optional: true }).then((sounds) => {
    state.sounds = sounds || [];
    const count = byId("sounds-nav-count");
    if (count) count.textContent = String(state.sounds.length);
  }).catch(() => {});
  api("/api/titles", { optional: true }).then((titles) => {
    state.titles = titles || [];
    const count = byId("titles-nav-count");
    if (count) count.textContent = String(state.titles.length);
  }).catch(() => {});
  api("/api/camera-moves", { optional: true }).then((moves) => {
    state.moves = moves || [];
    const count = byId("moves-nav-count");
    if (count) count.textContent = String(state.moves.length);
  }).catch(() => {});
  document.addEventListener("jobs-changed", () => renderJobs(true).catch(() => {}));
  const parameters = new URLSearchParams(window.location.search);
  const requestedTransition = parameters.get("transition");
  if (requestedTransition && state.transitions.some((item) => item.id === requestedTransition)) {
    renderTransitionDetail(requestedTransition);
    return;
  }
  showAddress({ replace: true });
}

/** Render whatever the address bar currently says. */
function showAddress({ replace = false } = {}) {
  const parameters = new URLSearchParams(window.location.search);
  const scene = parameters.get("scene");
  const shot = parameters.get("shot");
  if (scene && shot) {
    openCompare(scene, shot, { record: false });
    remember({ view: "compare", scene, shot }, { replace: true });
    return;
  }
  if (scene) {
    renderScene(scene, { record: false });
    remember({ view: "scene", scene }, { replace: true });
    return;
  }
  const requested = parameters.get("view");
  const view = requested && ROOMS.has(requested)
    ? requested
    : state.production ? "overview" : "library";
  state.currentView = view;
  state.sceneId = null;
  state.shotId = null;
  highlight(view);
  remember({ view }, { replace: true });
  draw(view);
}

window.addEventListener("popstate", () => showAddress({ replace: true }));
document.querySelectorAll("[data-view]").forEach((node) => node.addEventListener("click", () => setView(node.dataset.view)));
byId("quick-find").addEventListener("click", () => { byId("find-dialog").showModal(); byId("search-input").focus(); });
byId("find-close").addEventListener("click", () => byId("find-dialog").close());
byId("preview-close").addEventListener("click", () => byId("preview-dialog").close());
byId("search-form").addEventListener("submit", (event) => { event.preventDefault(); const query = byId("search-input").value.trim(); if (query) runSearch(query); });
document.addEventListener("keydown", (event) => {
  if (event.key === "/" && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) {
    event.preventDefault(); byId("find-dialog").showModal(); byId("search-input").focus();
  }
});

start().catch((error) => {
  byId("workspace").textContent = `Could not open production: ${error.message}`;
});
