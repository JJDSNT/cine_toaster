const state = {
  project: null,
  production: null,
  transitions: [],
  currentView: "overview",
  libraryPath: null,
};

const byId = (id) => document.getElementById(id);
const el = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
};

async function api(path, { optional = false } = {}) {
  const response = await fetch(path);
  if (!response.ok) {
    if (optional) return null;
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function label(value) {
  return String(value || "").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function statusPill(status) {
  return el("span", `status status-${status}`, label(status));
}

function metric(value, name, detail = "") {
  const card = el("article", "metric-card");
  card.append(el("strong", "metric-value", value), el("span", "metric-name", name));
  if (detail) card.append(el("small", "metric-detail", detail));
  return card;
}

function button(text, action, className = "quiet-button") {
  const node = el("button", className, text);
  node.type = "button";
  node.addEventListener("click", action);
  return node;
}

function sectionHeading(eyebrow, title, detail = "") {
  const heading = el("div", "section-heading");
  const copy = el("div");
  copy.append(el("span", "eyebrow", eyebrow), el("h2", "", title));
  if (detail) copy.append(el("p", "section-detail", detail));
  heading.append(copy);
  return heading;
}

function setView(view) {
  state.currentView = view;
  document.querySelectorAll("[data-view]").forEach((node) => {
    node.classList.toggle("active", node.dataset.view === view);
  });
  if (view === "overview") renderOverview();
  if (view === "scenes") renderScenes();
  if (view === "review") renderReview();
  if (view === "transitions") renderTransitions();
  if (view === "library") renderLibrary(state.project.id);
  byId("workspace").focus();
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
  root.append(hero, metrics, phases, columns, sceneStrip);
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

async function renderScene(sceneId) {
  const scene = await api(`/api/scene?id=${encodeURIComponent(sceneId)}`);
  state.currentView = "scene";
  document.querySelectorAll("[data-view]").forEach((node) => node.classList.remove("active"));
  const root = byId("workspace");
  root.replaceChildren();

  const back = button("← All scenes", () => setView("scenes"), "back-button");
  const header = el("section", "scene-header");
  const copy = el("div");
  const meta = el("div", "scene-header-meta");
  meta.append(el("span", "scene-id", scene.id), statusPill(scene.status), el("span", "muted", scene.sequence));
  copy.append(meta, el("h1", "", scene.title), el("p", "hero-logline", scene.summary));
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

  const columns = el("section", "scene-columns");
  columns.append(renderShots(scene), renderDecisions(scene));
  root.append(columns, renderIterations(scene));
}

function renderShots(scene) {
  const panel = el("article", "panel");
  panel.append(sectionHeading("SHOTS", `${scene.shots.length} planned shots`, "Selection state and available takes."));
  const list = el("div", "shot-list");
  for (const shot of scene.shots) {
    const row = el("div", "shot-row");
    const copy = el("span", "shot-copy");
    copy.append(el("b", "", shot.id), el("strong", "", shot.label));
    row.append(copy, statusPill(shot.status), el("span", "take-count", `${shot.takes} takes`), el("strong", "selected-take", shot.selected_take || "—"));
    list.append(row);
  }
  if (!scene.shots.length) list.append(el("p", "empty-state", "Shots have not been broken down yet."));
  panel.append(list);
  return panel;
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
      visual.append(el("span", "", shot.id), el("strong", "", `${shot.takes} candidates`));
      card.append(visual, el("strong", "", shot.label), el("small", "", "No take selected"), button("Compare candidates", () => renderScene(scene.id), "primary-button"));
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
      precision mediump float;
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

function transitionVisual(transition, large = false) {
  const frame = el("div", large ? "transition-visual transition-visual-large" : "transition-visual");
  if (transition.kind === "webm") {
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

function renderTransitions() {
  const root = byId("workspace");
  root.replaceChildren();
  const heading = sectionHeading("TRANSITION BANK", "Transitions", "Preview a shared visual vocabulary and expose the same intent to production agents.");
  heading.classList.add("page-heading");
  root.append(heading);

  const categories = new Map();
  for (const transition of state.transitions) {
    if (!categories.has(transition.category)) categories.set(transition.category, []);
    categories.get(transition.category).push(transition);
  }
  for (const [category, transitions] of categories) {
    const section = el("section", "transition-section");
    section.append(sectionHeading("BANK", label(category), `${transitions.length} available`));
    const grid = el("div", "transition-grid");
    for (const transition of transitions) {
      const card = el("article", "transition-card");
      card.append(transitionVisual(transition));
      const copy = el("div", "transition-card-copy");
      const top = el("div", "transition-card-top");
      top.append(el("strong", "", transition.name), el("span", `energy energy-${transition.energy}`, transition.energy));
      copy.append(top, el("p", "", transition.description));
      const tags = el("div", "tag-list");
      transition.tags.slice(0, 4).forEach((tag) => tags.append(el("span", "tag", tag)));
      copy.append(tags, button("Inspect and guide AI", () => renderTransitionDetail(transition.id), "quiet-button"));
      card.append(copy);
      grid.append(card);
    }
    section.append(grid);
    root.append(section);
  }
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
  aiPanel.append(aiHeading, el("blockquote", "", transition.guidance));
  const facts = el("dl", "transition-facts");
  for (const [name, value] of [["Energy", transition.energy], ["Motion", transition.motion], ["Asset role", transition.webm_role], ["Origin", transition.origin], ["License", transition.license]]) {
    facts.append(el("dt", "", name), el("dd", "", label(value)));
  }
  aiPanel.append(facts);
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

async function start() {
  [state.project, state.production, state.transitions] = await Promise.all([
    api("/api/project"),
    api("/api/production", { optional: true }),
    api("/api/transitions"),
  ]);
  byId("project-name").textContent = state.production?.title || state.project.name;
  byId("project-root").textContent = state.project.root;
  byId("project-format").textContent = state.production?.format || "UNSTRUCTURED";
  byId("project-phase").textContent = label(state.production?.production?.current_phase || "Library only");
  byId("scene-nav-count").textContent = state.production?.metrics.total_scenes || 0;
  byId("review-nav-count").textContent = state.production?.metrics.attention_items || 0;
  byId("transition-nav-count").textContent = state.transitions.length;
  const parameters = new URLSearchParams(window.location.search);
  const requestedTransition = parameters.get("transition");
  if (requestedTransition && state.transitions.some((item) => item.id === requestedTransition)) {
    renderTransitionDetail(requestedTransition);
    return;
  }
  const requestedView = parameters.get("view");
  const availableViews = new Set(["overview", "scenes", "review", "transitions", "library"]);
  const initialView = requestedView && availableViews.has(requestedView)
    ? requestedView
    : state.production ? "overview" : "library";
  setView(initialView);
}

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
