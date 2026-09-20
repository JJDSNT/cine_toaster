// The version history of one scene: every assembled cut, what changed, what the
// author thought of it, and the takes it was built from.
//
// Watching two cuts and remembering which was better is the part of review that
// does not scale. Here the verdict is written down next to the version, the
// difference between any two is listed shot by shot, and going back to an
// earlier cut is one command rather than an archaeology session.

import { button, el, runCommand, sectionHeading, statusPill, toast } from "./ui.js";

const VERDICTS = [
  ["approved", "Approve"],
  ["rejected", "Reject"],
  ["not_sent", "Never shown"],
];

const state = { compare: [null, null] };

function verdictPill(verdict) {
  const status = {
    approved: "approved",
    rejected: "rejected",
    superseded: "waiting",
    not_sent: "waiting",
    pending: "proposed",
  }[verdict] || "waiting";
  return statusPill(status === "proposed" ? "in_review" : status);
}

function player(scene, assembly) {
  if (!assembly.media) return el("span", "take-placeholder", "No render registered");
  const video = el("video");
  video.src = `/media/${assembly.media}`.replace(/\/+/g, "/");
  video.controls = true;
  video.preload = "none";
  return video;
}

function differences(first, second) {
  const shots = [...new Set([...Object.keys(first.takes), ...Object.keys(second.takes)])].sort();
  return shots
    .map((shotId) => ({
      shot_id: shotId,
      from: first.takes[shotId] || "",
      to: second.takes[shotId] || "",
    }))
    .filter((change) => change.from !== change.to);
}

function comparison(scene, assemblies) {
  const [firstId, secondId] = state.compare;
  const first = assemblies.find((item) => item.id === firstId);
  const second = assemblies.find((item) => item.id === secondId);
  const panel = el("div", "version-comparison");

  const pickers = el("div", "comparison-slot-head");
  for (const position of [0, 1]) {
    const picker = el("select", "take-picker");
    const empty = el("option", "", position === 0 ? "— earlier version —" : "— later version —");
    empty.value = "";
    picker.append(empty);
    for (const assembly of assemblies) {
      const option = el("option", "", `${assembly.id} · ${assembly.verdict}`);
      option.value = assembly.id;
      if (assembly.id === state.compare[position]) option.selected = true;
      picker.append(option);
    }
    picker.addEventListener("change", () => {
      state.compare[position] = picker.value || null;
      panel.replaceWith(comparison(scene, assemblies));
    });
    pickers.append(picker);
  }
  panel.append(pickers);

  if (!first || !second) {
    panel.append(el("p", "empty-state", "Choose two versions to see what changed between them."));
    return panel;
  }

  const players = el("div", "comparison-grid");
  for (const assembly of [first, second]) {
    const slot = el("div", "comparison-slot");
    const head = el("div", "comparison-slot-head");
    head.append(el("strong", "", assembly.id), verdictPill(assembly.verdict));
    slot.append(head, player(scene, assembly));
    if (assembly.summary) slot.append(el("p", "take-note", assembly.summary));
    if (assembly.note) slot.append(el("small", "muted", `Verdict: ${assembly.note}`));
    players.append(slot);
  }
  panel.append(players);

  const changes = differences(first, second);
  const list = el("div", "shot-list");
  if (!changes.length) {
    list.append(el("p", "empty-state", "Both versions use exactly the same takes."));
  }
  for (const change of changes) {
    const row = el("div", "shot-row");
    row.append(
      el("span", "shot-copy", change.shot_id),
      el("span", "take-count", change.from || "—"),
      el("span", "muted", "→"),
      el("strong", "selected-take", change.to || "—"),
    );
    list.append(row);
  }
  panel.append(
    el("div", "section-heading", ""),
    el("small", "muted", `${changes.length} shot(s) differ`),
    list,
  );
  return panel;
}

export function renderVersions(scene, { onChanged }) {
  const assemblies = scene.assemblies || [];
  const panel = el("section", "panel wide-panel");
  const approved = scene.approved_assembly;
  panel.append(
    sectionHeading(
      "VERSIONS",
      approved ? `Current cut: ${approved.id}` : "No approved cut yet",
      "Every assembled version, its verdict, and the takes it was built from.",
    ),
  );

  if (!assemblies.length) {
    panel.append(
      el(
        "p",
        "empty-state",
        "No versions recorded. Register one with: toast version record <project> " +
          `${scene.id} v1 --media <path> --summary "what changed"`,
      ),
    );
    return panel;
  }

  const commit = async (command, payload, message) => {
    try {
      await runCommand(command, { scene_id: scene.id, expected_revision: scene.revision, ...payload });
      toast(message, "good");
      await onChanged();
    } catch (error) {
      if (error.code === "revision_conflict") {
        toast("Someone else changed this scene first. Reloading.", "warn");
        await onChanged();
        return;
      }
      toast(error.message, "bad");
    }
  };

  const list = el("div", "finding-list");
  for (const assembly of assemblies) {
    const card = el("article", `finding-card finding-${assembly.verdict === "approved" ? "ok" : "warning"}`);
    const head = el("div", "take-head");
    head.append(
      el("strong", "", assembly.id),
      verdictPill(assembly.verdict),
      el("small", "muted", assembly.created_at.slice(0, 16).replace("T", " ")),
      el("small", "muted", assembly.duration_seconds ? `${Math.round(assembly.duration_seconds)}s` : ""),
      el("small", "muted", `${Object.keys(assembly.takes).length} shots decided`),
    );
    card.append(head);
    if (assembly.summary) card.append(el("p", "take-note", assembly.summary));
    if (assembly.note) {
      card.append(el("p", "", `“${assembly.note}”`));
      if (assembly.reviewed_by) {
        card.append(el("small", "muted", `${assembly.reviewed_by.id} · ${assembly.reviewed_at.slice(0, 16).replace("T", " ")}`));
      }
    }
    if (assembly.media) {
      const details = el("details", "finding-why");
      details.append(el("summary", "", "Watch this version"));
      details.append(player(scene, assembly));
      card.append(details);
    }

    const actions = el("div", "take-actions");
    for (const [verdict, label] of VERDICTS) {
      if (assembly.verdict === verdict) continue;
      actions.append(
        button(label, () => {
          const note = window.prompt(`${label} ${assembly.id} — why?`, assembly.note || "");
          if (note === null) return;
          commit(
            "review_assembly",
            { assembly_id: assembly.id, verdict, note },
            `${assembly.id} marked ${verdict}.`,
          );
        }),
      );
    }
    actions.append(
      button(
        "Restore these takes",
        () => {
          const rationale = window.prompt(
            `Roll the scene back to the takes ${assembly.id} was built from. Why?`,
            "",
          );
          if (rationale === null) return;
          commit(
            "restore_assembly",
            { assembly_id: assembly.id, rationale },
            `Selections restored from ${assembly.id}.`,
          );
        },
        assembly.verdict === "approved" ? "quiet-button" : "primary-button",
      ),
    );
    card.append(actions);
    list.append(card);
  }
  panel.append(list);

  if (assemblies.length > 1) {
    if (!state.compare[0] && !state.compare[1]) {
      state.compare = [assemblies[1].id, assemblies[0].id];
    }
    panel.append(
      sectionHeading("COMPARE", "What changed between two cuts"),
      comparison(scene, assemblies),
    );
  }
  return panel;
}
