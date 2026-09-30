// What a model was given, or will be: the pictures, the frames they guide,
// the prompt by shot, the seed, the cost. Read from the record kept beside a
// clip (its .provenance.json and .job.json) or from a plan not yet sent, so
// the same view answers "what will go" and "what went" (CT-0037, CT-0040).

import { el } from "./ui.js";

const FPS = 24;

const media = (path) => `/media/${path}`.replace(/\/+/g, "/");
const money = (value) => (value == null ? "" : `US$ ${Number(value).toFixed(3)}`);

function fact(name, value) {
  if (value === undefined || value === null || value === "") return null;
  const item = el("span", "sent-fact");
  item.append(el("small", "", name), el("strong", "", String(value)));
  return item;
}

function facts(entries) {
  const row = el("div", "sent-facts");
  for (const [name, value] of entries) {
    const item = fact(name, value);
    if (item) row.append(item);
  }
  return row.childElementCount ? row : null;
}

function gpuSeconds(job) {
  if (!job || (job.executionTime == null && job.delayTime == null)) return "";
  const run = (job.executionTime || 0) / 1000;
  const wait = (job.delayTime || 0) / 1000;
  return `${run.toFixed(0)} s running, ${wait.toFixed(0)} s waiting`;
}

// The starting picture and each guide, with the frame it holds.
function pictures(record) {
  const strip = el("div", "sent-pictures");
  const guides = record.guides || [];
  const start = record.image;
  const shown = guides.length ? guides : start ? [{ role: "first", path: start, frame: 0 }] : [];
  for (const guide of shown) {
    const card = el("figure", "sent-picture");
    const image = el("img");
    image.src = media(guide.path);
    image.alt = guide.path;
    const isStart = guide.path === start && guide.frame === 0;
    const role = guide.role === "first" ? "first shot" : guide.role;
    const when = `frame ${guide.frame} · ${(guide.frame / FPS).toFixed(2)} s`;
    const caption = el("figcaption");
    caption.append(
      el("strong", "", isStart ? "Starts from, and guides" : "Guides"),
      el("span", "", `${role} · ${when}`),
      el("small", "", guide.path.split("/").pop() + (guide.digest ? ` · ${guide.digest}` : "")),
    );
    card.append(image, caption);
    strip.append(card);
  }
  return strip.childElementCount ? strip : null;
}

// The prompt by shot, when it was kept in pieces; whole otherwise.
function prompt(record) {
  const box = el("div", "sent-prompt");
  const sections = record.prompt_sections || [];
  if (sections.length) {
    for (const section of sections) {
      if (!section.text) continue;
      const row = el("p", "sent-section");
      row.append(el("span", "sent-shot", section.shot || "Whole block"), el("span", "", section.text));
      box.append(row);
    }
  } else if (record.prompt) {
    box.append(el("p", "sent-whole", record.prompt));
  }
  if (!box.childElementCount) return null;
  const copy = el("button", "quiet-button sent-copy", "Copy prompt");
  copy.type = "button";
  copy.addEventListener("click", () => navigator.clipboard?.writeText(record.prompt || ""));
  box.append(copy);
  return box;
}

function generation(record, { plan = false } = {}) {
  const view = el("div", "sent-view");
  const job = record.job || {};
  const cost = plan ? null : record.cost_usd;
  const row = facts([
    ["Model", record.model || "ltx-2.5"],
    ["Length", record.seconds ? `${record.seconds} s` : ""],
    ["Seed", record.seed],
    [plan ? "Estimate" : "Estimated", money(record.estimate_usd)],
    ["Cost", cost != null ? money(cost) : ""],
    ["GPU", gpuSeconds(job)],
    ["Budget", plan && record.limit_usd != null
      ? (record.limit_usd ? `US$ ${record.spent_usd.toFixed(2)} of ${record.limit_usd.toFixed(2)} spent` : "not set")
      : ""],
  ]);
  if (row) view.append(row);
  const strip = pictures(record);
  if (strip) view.append(strip);
  const text = prompt(record);
  if (text) view.append(text);
  for (const note of record.notes || []) view.append(el("p", "join-finding warning", note));
  return view;
}

// A picture repainted by an editor: what it edited, whose faces, and the words.
function derivation(record, { plan = false } = {}) {
  const view = el("div", "sent-view");
  const score = record.edge_score;
  const row = facts([
    ["Model", record.model],
    ["Size", record.width ? `${record.width}×${record.height}` : ""],
    ["Seed", record.seed],
    [plan ? "Estimate" : "Estimated", money(record.estimate_usd)],
    ["Cost", plan ? "" : money(record.cost_usd)],
    ["GPU", gpuSeconds(record.job)],
    ["Edges kept", score != null ? `${score}${score < 17 ? " (recomposed)" : ""}` : ""],
    ["Budget", plan && record.limit_usd != null
      ? (record.limit_usd ? `US$ ${record.spent_usd.toFixed(2)} of ${record.limit_usd.toFixed(2)} spent` : "not set")
      : ""],
  ]);
  if (row) view.append(row);
  const strip = el("div", "sent-pictures");
  const figure = (path, title, detail, digest) => {
    const card = el("figure", "sent-picture");
    const image = el("img");
    image.src = media(path);
    image.alt = path;
    const caption = el("figcaption");
    caption.append(el("strong", "", title), el("span", "", detail),
      el("small", "", path.split("/").pop() + (digest ? ` · ${digest}` : "")));
    card.append(image, caption);
    return card;
  };
  if (record.source) strip.append(figure(record.source.path, "Image 1: edited", "its geometry is kept", record.source.digest));
  (record.references || []).forEach((ref, index) => strip.append(figure(ref.path, `Image ${index + 2}: identity`,
    `${ref.member}${ref.variant ? ` (${ref.variant})` : ""}`, ref.digest)));
  if (strip.childElementCount) view.append(strip);
  if (record.request) {
    const box = el("div", "sent-prompt");
    const asked = el("p", "sent-section");
    asked.append(el("span", "sent-shot", "Asked for"), el("span", "", record.request));
    box.append(asked);
    const full = el("details", "sent-details");
    full.append(el("summary", "", "The whole prompt, with the geometry clauses"), el("p", "sent-whole", record.prompt || ""));
    box.append(full);
    view.append(box);
  }
  if (!plan && score != null) {
    view.append(el("p", "muted", "The edge score catches a recomposed frame, not a subject that moved: look before approving."));
  }
  for (const note of record.notes || []) view.append(el("p", "join-finding warning", note));
  return view;
}

function outside(job) {
  const view = el("div", "sent-view");
  view.append(el("p", "muted", "Made outside Cine Toaster: the platform's job is recorded, what was sent to the model is not."));
  const row = facts([["Job", job.id], ["Status", job.status], ["GPU", gpuSeconds(job)], ["Endpoint", job.endpoint]]);
  if (row) view.append(row);
  return view;
}

function slice(record) {
  const view = el("div", "sent-view");
  const [start, end] = record.seconds || [];
  view.append(el("p", "", `Cut from block ${record.block} (${(record.clip || "").split("/").pop()}), ${start}–${end} s; cuts ${record.method}.`));
  if (record.note) view.append(el("p", "muted", record.note));
  if (record.block_generation) view.append(generation({ job: record.generation, ...record.block_generation }));
  else if (record.generation) view.append(outside(record.generation));
  return view;
}

function revoice(record) {
  const view = el("div", "sent-view");
  view.append(el("p", "", `${record.speaker}'s speech from take ${record.from_take}, converted to ${record.member}'s recording.`));
  if (record.reference) {
    const audio = el("audio");
    audio.src = media(record.reference);
    audio.controls = true;
    audio.preload = "none";
    view.append(audio);
  }
  const likeness = record.similarity;
  const row = facts([
    ["Likeness", likeness ? `${likeness.before} → ${likeness.after}` : ""],
    ["Engine", record.engine],
    ["Separation", record.separation],
    ["CPU", record.convert_seconds != null ? `${record.separate_seconds + record.convert_seconds} s` : ""],
  ]);
  if (row) view.append(row);
  return view;
}

// The view for any record; null when nothing was recorded.
export function sentView(record, { plan = false } = {}) {
  if (!record || !Object.keys(record).length) return null;
  if (record.kind === "picture-derivation" || (plan && record.source && record.references)) {
    return derivation(record, { plan });
  }
  if (plan || record.kind === "block-generation" || record.kind === "shot-generation") return generation(record, { plan });
  if (record.kind === "block-slice") return slice(record);
  if (record.kind === "voice-conversion") return revoice(record);
  if (record.job && Object.keys(record).length === 1) return outside(record.job);
  return null;
}

function viewable(record) {
  if (!record || !Object.keys(record).length) return false;
  if (["block-generation", "shot-generation", "block-slice", "voice-conversion", "picture-derivation"].includes(record.kind)) return true;
  return Boolean(record.job) && Object.keys(record).length === 1;
}

// Collapsed under a card, so the pictures load only when asked for; null when
// the record has no view of its own.
export function sentDetails(record, title = "What was sent") {
  if (!viewable(record)) return null;
  const details = el("details", "sent-details");
  details.append(el("summary", "", title));
  details.addEventListener("toggle", () => {
    if (!details.open || details.dataset.filled) return;
    details.dataset.filled = "1";
    details.append(sentView(record));
  });
  return details;
}
