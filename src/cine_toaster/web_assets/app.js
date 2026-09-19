const state = {
  project: null,
  current: null,
  selected: null,
  comparison: [],
};

const byId = (id) => document.getElementById(id);

async function api(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json();
}

function humanSize(bytes) {
  let value = Number(bytes || 0);
  const units = ["B", "KiB", "MiB", "GiB", "TiB"];
  for (const unit of units) {
    if (value < 1024 || unit === "TiB") {
      return unit === "B" ? `${value} B` : `${value.toFixed(1)} ${unit}`;
    }
    value /= 1024;
  }
}

function mediaUrl(item) {
  return `/media/${item.relative_path.split("/").map(encodeURIComponent).join("/")}`;
}

function iconFor(item) {
  if (item.kind === "scene") return "SC";
  if (item.kind === "take") return "TK";
  if (item.kind === "scene_version") return "V";
  if (item.kind === "shot_clip") return "CL";
  if (item.kind === "shot_still") return "ST";
  if (item.media_type === "video") return "▶";
  if (item.media_type === "image") return "▧";
  if (item.media_type === "audio") return "♪";
  if (item.media_type === "text") return "TXT";
  if (item.media_type === "document") return "DOC";
  return item.is_directory ? "DIR" : "FILE";
}

function canPreview(item) {
  return Boolean(item && !item.is_directory && item.media_type);
}

function createPreview(item, compact = false) {
  const container = document.createElement("div");
  container.className = compact ? "media-preview compact" : "media-preview";
  const url = mediaUrl(item);
  if (item.media_type === "image") {
    const image = document.createElement("img");
    image.src = url;
    image.alt = item.name;
    container.append(image);
  } else if (item.media_type === "video") {
    const video = document.createElement("video");
    video.src = url;
    video.controls = true;
    video.preload = "metadata";
    container.append(video);
  } else if (item.media_type === "audio") {
    const audio = document.createElement("audio");
    audio.src = url;
    audio.controls = true;
    audio.preload = "metadata";
    container.append(audio);
  } else if (item.extension === ".pdf") {
    const frame = document.createElement("iframe");
    frame.src = url;
    frame.title = item.name;
    container.append(frame);
  } else if (item.media_type === "text") {
    const pre = document.createElement("pre");
    pre.textContent = "Carregando…";
    fetch(url).then((response) => response.text()).then((text) => {
      pre.textContent = text;
    });
    container.append(pre);
  } else {
    container.textContent = "Pré-visualização indisponível.";
  }
  return container;
}

function cardFor(item) {
  const card = document.createElement("button");
  card.type = "button";
  card.className = "item-card";
  card.dataset.id = item.id;

  const visual = document.createElement("div");
  visual.className = "card-visual";
  if (item.media_type === "image") {
    const image = document.createElement("img");
    image.src = mediaUrl(item);
    image.alt = "";
    image.loading = "lazy";
    visual.append(image);
  } else {
    const icon = document.createElement("span");
    icon.className = "card-icon";
    icon.textContent = iconFor(item);
    visual.append(icon);
  }

  const body = document.createElement("div");
  body.className = "card-body";
  const kind = document.createElement("span");
  kind.className = "card-kind";
  kind.textContent = item.kind.replaceAll("_", " ");
  const name = document.createElement("strong");
  name.textContent = item.name;
  body.append(kind, name);
  if (item.snippet) {
    const snippet = document.createElement("p");
    snippet.textContent = item.snippet;
    body.append(snippet);
  }
  card.append(visual, body);
  card.addEventListener("click", () => item.is_directory ? navigate(item.id) : inspect(item.id));
  return card;
}

function renderItems(items) {
  const grid = byId("content-grid");
  grid.replaceChildren(...items.map(cardFor));
  byId("empty-state").hidden = items.length > 0;
  byId("item-count").textContent = `${items.length} ${items.length === 1 ? "item" : "itens"}`;
}

function renderBreadcrumbs(ancestors) {
  const fragment = document.createDocumentFragment();
  ancestors.forEach((item, index) => {
    if (index) fragment.append(" / ");
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = item.name;
    button.addEventListener("click", () => navigate(item.id));
    fragment.append(button);
  });
  byId("breadcrumbs").replaceChildren(fragment);
}

async function navigate(itemId) {
  const [item, children] = await Promise.all([
    api(`/api/item?id=${encodeURIComponent(itemId)}`),
    api(`/api/items?parent=${encodeURIComponent(itemId)}`),
  ]);
  state.current = item;
  byId("view-title").textContent = item.name;
  byId("view-kind").textContent = item.kind.replaceAll("_", " ");
  renderBreadcrumbs(item.ancestors);
  renderItems(children);
}

async function inspect(itemId) {
  const item = await api(`/api/item?id=${encodeURIComponent(itemId)}`);
  state.selected = item;
  byId("inspector-empty").hidden = true;
  byId("inspector-content").hidden = false;
  byId("inspect-kind").textContent = item.kind.replaceAll("_", " ");
  byId("inspect-name").textContent = item.name;
  byId("preview").replaceChildren(createPreview(item));

  const values = [
    ["Caminho", item.relative_path],
    ["Tipo", item.media_type || item.kind],
    ["Tamanho", humanSize(item.size)],
  ];
  const fragment = document.createDocumentFragment();
  for (const [label, value] of values) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    fragment.append(dt, dd);
  }
  byId("inspect-metadata").replaceChildren(fragment);

  const compareButton = byId("compare-add");
  compareButton.disabled = !canPreview(item);
  compareButton.textContent = state.comparison.some((entry) => entry.id === item.id)
    ? "Remover da comparação"
    : "Adicionar à comparação";
}

function updateComparison() {
  byId("compare-count").textContent = String(state.comparison.length);
  byId("compare-open").disabled = state.comparison.length < 2;
  if (state.selected) inspect(state.selected.id);
}

function toggleComparison() {
  const item = state.selected;
  if (!canPreview(item)) return;
  const existing = state.comparison.findIndex((entry) => entry.id === item.id);
  if (existing >= 0) {
    state.comparison.splice(existing, 1);
  } else {
    if (state.comparison.length >= 4) state.comparison.shift();
    state.comparison.push(item);
  }
  updateComparison();
}

function openComparison() {
  const panes = state.comparison.map((item) => {
    const pane = document.createElement("section");
    pane.className = "compare-pane";
    pane.append(createPreview(item, true));
    const heading = document.createElement("div");
    heading.className = "compare-pane-heading";
    const title = document.createElement("strong");
    title.textContent = item.name;
    const path = document.createElement("span");
    path.textContent = item.relative_path;
    heading.append(title, path);
    pane.append(heading);
    return pane;
  });
  byId("compare-grid").replaceChildren(...panes);
  byId("compare-dialog").showModal();
}

async function runSearch(query) {
  const results = await api(`/api/search?q=${encodeURIComponent(query)}`);
  byId("view-title").textContent = `Busca: ${query}`;
  byId("view-kind").textContent = "RESULTADOS";
  byId("breadcrumbs").replaceChildren();
  renderItems(results);
}

async function start() {
  state.project = await api("/api/project");
  byId("project-name").textContent = state.project.name;
  byId("project-stats").innerHTML = `
    <span>${state.project.file_count.toLocaleString("pt-BR")} arquivos</span>
    <span>${humanSize(state.project.total_bytes)}</span>
    <span>${state.project.adapter}</span>
  `;

  const rootChildren = await api(`/api/items?parent=${encodeURIComponent(state.project.id)}`);
  const navigation = rootChildren.filter((item) => item.is_directory).map((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.innerHTML = `<span>${iconFor(item)}</span><strong>${item.name}</strong>`;
    button.addEventListener("click", () => navigate(item.id));
    return button;
  });
  byId("root-navigation").replaceChildren(...navigation);
  await navigate(state.project.id);
}

byId("search-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const query = byId("search-input").value.trim();
  if (query) runSearch(query);
});
byId("compare-add").addEventListener("click", toggleComparison);
byId("compare-open").addEventListener("click", openComparison);
byId("compare-close").addEventListener("click", () => byId("compare-dialog").close());
byId("compare-clear").addEventListener("click", () => {
  state.comparison = [];
  updateComparison();
  byId("compare-dialog").close();
});
byId("compare-play").addEventListener("click", () => {
  const media = [...byId("compare-grid").querySelectorAll("video, audio")];
  for (const element of media) {
    element.currentTime = 0;
    element.play();
  }
});

start().catch((error) => {
  byId("content-grid").textContent = `Erro ao abrir projeto: ${error.message}`;
});

