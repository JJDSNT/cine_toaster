// The comparison room: two or more alternatives for one shot, side by side,
// and the single act of choosing one.
//
// Generation is probabilistic, so a shot arrives as several plausible takes.
// Collapsing them immediately loses the comparison the director actually needs
// to make, and the reason for the choice. Here the alternatives stay, the
// choice is explicit, and the rationale is stored with it.

import { button, el, runCommand, sectionHeading, statusPill, toast } from "./ui.js";

const state = {
  scene: null,
  shot: null,
  slots: ["", ""],
  muted: true,
};

// Take paths are recorded relative to the project root, because that is the
// only anchor shared by the runtime, the interface, and the assembly tool.
function mediaUrl(scene, take) {
  if (!take.media) return "";
  return `/media/${take.media}`.replace(/\/+/g, "/");
}

function posterUrl(scene, take) {
  if (!take.poster) return "";
  return `/media/${take.poster}`.replace(/\/+/g, "/");
}

function takeSurface(scene, take, { large = false } = {}) {
  const frame = el("div", large ? "take-surface take-surface-large" : "take-surface");
  const url = mediaUrl(scene, take);
  if (!url) {
    frame.append(el("span", "take-placeholder", "No media registered"));
    return frame;
  }
  if (/\.(png|jpe?g|webp|avif|gif)$/i.test(url)) {
    const image = el("img");
    image.src = url;
    image.alt = take.label;
    image.loading = "lazy";
    frame.append(image);
    return frame;
  }
  const video = el("video");
  video.src = url;
  video.controls = large;
  video.loop = true;
  video.muted = state.muted;
  video.playsInline = true;
  video.preload = "metadata";
  const poster = posterUrl(scene, take);
  if (poster) video.poster = poster;
  video.dataset.takeId = take.id;
  frame.append(video);
  if (!large) {
    frame.addEventListener("mouseenter", () => video.play().catch(() => {}));
    frame.addEventListener("mouseleave", () => {
      video.pause();
      video.currentTime = 0;
    });
  }
  return frame;
}

function provenanceLine(take) {
  const entries = Object.entries(take.provenance || {});
  if (!entries.length) return null;
  const text = entries.map(([key, value]) => `${key} ${value}`).join(" · ");
  return el("small", "take-provenance", text);
}

function takeCard(scene, shot, take, { onCompare, onSelect }) {
  const card = el("article", "take-card");
  if (take.selected) card.classList.add("take-selected");
  if (take.status === "rejected") card.classList.add("take-rejected");

  card.append(takeSurface(scene, take));
  const head = el("div", "take-head");
  head.append(el("strong", "", take.id), el("span", "take-label", take.label));
  if (take.selected) head.append(el("span", "status status-selected", "Selected"));
  else if (take.status !== "candidate") head.append(statusPill(take.status));
  card.append(head);

  if (take.note) card.append(el("p", "take-note", take.note));

  const facts = el("div", "take-facts");
  if (take.duration_seconds) facts.append(el("span", "", `${take.duration_seconds}s`));
  if (take.cost_usd) facts.append(el("span", "", `$${take.cost_usd.toFixed(2)}`));
  if (facts.childElementCount) card.append(facts);

  const provenance = provenanceLine(take);
  if (provenance) card.append(provenance);

  const actions = el("div", "take-actions");
  actions.append(button("Compare", () => onCompare(take.id)));
  if (take.selectable && !take.selected) {
    actions.append(button("Select", () => onSelect(take.id), "primary-button"));
  }
  card.append(actions);
  return card;
}

function comparisonSlot(scene, shot, position, onPick) {
  const takeId = state.slots[position];
  const take = shot.takes.find((item) => item.id === takeId);
  const slot = el("div", "comparison-slot");
  const head = el("div", "comparison-slot-head");
  head.append(el("span", "eyebrow", position === 0 ? "A" : "B"));

  const picker = el("select", "take-picker");
  const empty = el("option", "", "— choose an alternative —");
  empty.value = "";
  picker.append(empty);
  for (const candidate of shot.takes) {
    const option = el("option", "", `${candidate.id} · ${candidate.label}`);
    option.value = candidate.id;
    if (candidate.id === takeId) option.selected = true;
    picker.append(option);
  }
  picker.addEventListener("change", () => onPick(position, picker.value));
  head.append(picker);
  slot.append(head);

  if (!take) {
    slot.append(el("div", "take-surface take-surface-large", ""));
    return slot;
  }
  slot.append(takeSurface(scene, take, { large: true }));
  const foot = el("div", "comparison-slot-foot");
  foot.append(el("strong", "", take.label));
  if (take.note) foot.append(el("p", "take-note", take.note));
  slot.append(foot);
  return slot;
}

function syncedControls(root) {
  const videos = [...root.querySelectorAll(".comparison-slot video")];
  if (videos.length < 2) return null;
  const bar = el("div", "compare-controls");
  bar.append(
    button("Play both", () => videos.forEach((video) => video.play().catch(() => {}))),
    button("Pause", () => videos.forEach((video) => video.pause())),
    button("Restart", () => videos.forEach((video) => {
      video.currentTime = 0;
      video.play().catch(() => {});
    })),
    button(state.muted ? "Unmute" : "Mute", () => {
      state.muted = !state.muted;
      videos.forEach((video) => {
        video.muted = state.muted;
      });
      bar.replaceWith(syncedControls(root));
    }),
  );
  return bar;
}

function decisionForm(scene, shot, onCommit) {
  const form = el("form", "decision-form");
  const field = el("input", "rationale-input");
  field.type = "text";
  field.name = "rationale";
  field.placeholder = "Why this take? (kept with the decision)";
  field.autocomplete = "off";

  const submit = el("button", "primary-button", "Select A");
  submit.type = "submit";
  const submitB = el("button", "primary-button", "Select B");
  submitB.type = "button";

  const commit = (position) => {
    const takeId = state.slots[position];
    if (!takeId) {
      toast("Choose an alternative in that slot first.", "warn");
      return;
    }
    onCommit(takeId, field.value.trim());
  };
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    commit(0);
  });
  submitB.addEventListener("click", () => commit(1));

  form.append(field, submit, submitB);
  if (shot.selection) {
    form.append(
      button("Clear selection", () => onCommit(null, field.value.trim()), "quiet-button"),
    );
  }
  return form;
}

function decisionHistory(scene, shot) {
  const entries = (scene.decision_log || []).filter((entry) => entry.shot_id === shot.id);
  const panel = el("article", "panel");
  panel.append(
    sectionHeading("HISTORY", "What was decided here", "Superseded choices stay on the record."),
  );
  if (!entries.length) {
    panel.append(el("p", "empty-state", "No committed decision for this shot yet."));
    return panel;
  }
  const list = el("div", "decision-list");
  for (const entry of entries) {
    const card = el("article", "decision-card");
    const headline = entry.take_id
      ? `${entry.previous_take_id ? `${entry.previous_take_id} → ` : ""}${entry.take_id}`
      : `cleared ${entry.previous_take_id || ""}`;
    card.append(
      statusPill(entry.kind === "take.selected" ? "selected" : "waiting"),
      el("strong", "", headline),
      el("small", "muted", `${entry.actor?.id || "unknown"} · ${entry.decided_at?.slice(0, 19).replace("T", " ")}`),
    );
    if (entry.rationale) card.append(el("p", "", entry.rationale));
    list.append(card);
  }
  panel.append(list);
  return panel;
}

export function renderCompare(root, scene, shot, { onBack, onChanged }) {
  state.scene = scene;
  state.shot = shot;

  const selectable = shot.takes.filter((take) => take.selectable);
  const preferred = shot.selected_take || selectable[0]?.id || "";
  const alternate = selectable.find((take) => take.id !== preferred)?.id || "";
  if (!shot.takes.some((take) => take.id === state.slots[0])) state.slots[0] = preferred;
  if (!shot.takes.some((take) => take.id === state.slots[1])) state.slots[1] = alternate;

  const draw = () => {
    root.replaceChildren();
    root.append(button("← Scene", onBack, "back-button"));

    const header = el("section", "scene-header");
    const copy = el("div");
    const meta = el("div", "scene-header-meta");
    meta.append(
      el("span", "scene-id", shot.id),
      statusPill(shot.status),
      el("span", "muted", `${scene.id} · ${scene.title}`),
    );
    copy.append(meta, el("h1", "", shot.label));
    if (shot.description) copy.append(el("p", "hero-logline", shot.description));
    const facts = el("div", "scene-facts");
    facts.append(
      metricLike(String(shot.takes.length), "Alternatives"),
      metricLike(shot.selected_take || "—", "Selected"),
      metricLike(shot.camera || "—", "Camera"),
    );
    header.append(copy, facts);
    root.append(header);

    const comparison = el("section", "panel wide-panel");
    comparison.append(
      sectionHeading(
        "COMPARE",
        "Two alternatives, one choice",
        "Nothing is discarded by choosing. The unselected takes stay available.",
      ),
    );
    const slots = el("div", "comparison-grid");
    const pick = (position, takeId) => {
      state.slots[position] = takeId;
      draw();
    };
    slots.append(comparisonSlot(scene, shot, 0, pick), comparisonSlot(scene, shot, 1, pick));
    comparison.append(slots);
    const controls = syncedControls(comparison);
    if (controls) comparison.append(controls);
    comparison.append(decisionForm(scene, shot, commit));
    root.append(comparison);

    const gallery = el("section", "panel wide-panel");
    gallery.append(
      sectionHeading("ALTERNATIVES", `${shot.takes.length} registered takes`, "Hover a card to preview it."),
    );
    const grid = el("div", "take-grid");
    for (const take of shot.takes) {
      grid.append(
        takeCard(scene, shot, take, {
          onCompare: (takeId) => pick(state.slots[0] === takeId ? 1 : 0, takeId),
          onSelect: (takeId) => commit(takeId, ""),
        }),
      );
    }
    if (!shot.takes.length) {
      grid.append(el("p", "empty-state", "No alternatives are registered for this shot yet."));
    }
    gallery.append(grid);
    root.append(gallery, decisionHistory(scene, shot));
  };

  const commit = async (takeId, rationale) => {
    try {
      if (takeId === null) {
        await runCommand("clear_selection", {
          scene_id: scene.id,
          shot_id: shot.id,
          expected_revision: scene.revision,
          rationale,
        });
        toast(`Cleared the selection on ${shot.id}.`);
      } else {
        await runCommand("select_take", {
          scene_id: scene.id,
          shot_id: shot.id,
          take_id: takeId,
          expected_revision: scene.revision,
          rationale,
        });
        toast(`${takeId} selected for ${shot.id}.`, "good");
      }
      await onChanged();
    } catch (error) {
      if (error.code === "revision_conflict") {
        toast("Someone else decided this scene first. Reloading the newer state.", "warn");
        await onChanged();
        return;
      }
      toast(error.message, "bad");
    }
  };

  draw();
}

function metricLike(value, name) {
  const card = el("article", "metric-card");
  card.append(el("strong", "metric-value", value), el("span", "metric-name", name));
  return card;
}
