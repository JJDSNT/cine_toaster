// Shared DOM and transport primitives used by every room.

export const byId = (id) => document.getElementById(id);

export const el = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
};

export async function api(path, { optional = false } = {}) {
  const response = await fetch(path);
  if (!response.ok) {
    if (optional) return null;
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

export class CommandError extends Error {
  constructor(code, message, details = {}) {
    super(message);
    this.code = code;
    this.details = details;
  }
}

// Every production mutation goes through this one call. The browser never
// writes project files; it asks the runtime to run a named command.
export async function runCommand(command, payload) {
  const response = await fetch("/api/commands", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command, ...payload }),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = body.error || {};
    throw new CommandError(error.code || "error", error.message || "Command failed", error);
  }
  return body;
}

export function label(value) {
  return String(value || "").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function statusPill(status) {
  return el("span", `status status-${status}`, label(status));
}

export function metric(value, name, detail = "") {
  const card = el("article", "metric-card");
  card.append(el("strong", "metric-value", value), el("span", "metric-name", name));
  if (detail) card.append(el("small", "metric-detail", detail));
  return card;
}

export function button(text, action, className = "quiet-button") {
  const node = el("button", className, text);
  node.type = "button";
  node.addEventListener("click", action);
  return node;
}

export function sectionHeading(eyebrow, title, detail = "") {
  const heading = el("div", "section-heading");
  const copy = el("div");
  copy.append(el("span", "eyebrow", eyebrow), el("h2", "", title));
  if (detail) copy.append(el("p", "section-detail", detail));
  heading.append(copy);
  return heading;
}

export function toast(message, tone = "info") {
  let host = byId("toast-host");
  if (!host) {
    host = el("div", "toast-host");
    host.id = "toast-host";
    document.body.append(host);
  }
  const node = el("div", `toast toast-${tone}`, message);
  host.append(node);
  setTimeout(() => node.remove(), 5200);
}
