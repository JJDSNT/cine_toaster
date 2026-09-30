// The directing assistant in every room of the control room (ADR 0018).
//
// The assistant itself is the React page /app/assistant.html, in an iframe on
// the same origin: this module only opens and closes the drawer, tells it what
// the room shows after every render, and follows what it asks -- a shot to
// point at, a room to open. Closing the drawer keeps the conversation.

const ORIGIN = window.location.origin;
let frame = null;
let ready = false;
let describe = () => ({ room: "control room", scene: "", focus: "", selected: "" });
let follow = () => {};
let pointed = "";

function post(message) {
  if (frame && ready) frame.contentWindow.postMessage(message, ORIGIN);
}

/** Mark the shot the assistant points at, wherever the room draws shots. */
function point() {
  document.querySelectorAll(".assistant-pointed").forEach((node) => node.classList.remove("assistant-pointed"));
  if (!pointed) return;
  document.querySelectorAll(`[data-shot-id="${CSS.escape(pointed)}"]`).forEach((node) => {
    node.classList.add("assistant-pointed");
  });
}

/** Call after a room renders: the assistant learns what is on screen now. */
export function tellAssistant() {
  post({ type: "cine-toaster:context", seen: describe() });
  point();
}

function open(drawer, toggle) {
  if (!frame) {
    frame = document.createElement("iframe");
    frame.src = "/app/assistant.html";
    frame.title = "Assistant";
    drawer.append(frame);
  }
  drawer.hidden = false;
  toggle.classList.add("on");
}

/** Show the Assistant button when the runtime has the assistant on. */
export async function startAssistant({ seen, navigate }) {
  describe = seen;
  follow = navigate;
  const response = await fetch("/api/copilotkit/info").catch(() => null);
  if (!response || !response.ok) return;
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "assistant-button";
  toggle.textContent = "Assistant";
  const drawer = document.createElement("aside");
  drawer.className = "assistant-drawer-frame";
  drawer.hidden = true;
  toggle.addEventListener("click", () => {
    if (drawer.hidden) open(drawer, toggle);
    else {
      drawer.hidden = true;
      toggle.classList.remove("on");
    }
  });
  // Beside "Find anything" in the header; floating only if a page has no header.
  const find = document.getElementById("quick-find");
  if (find) {
    const actions = document.createElement("div");
    actions.className = "header-actions";
    find.replaceWith(actions);
    actions.append(toggle, find);
    toggle.classList.add("in-header");
  }
  document.body.append(...(find ? [drawer] : [toggle, drawer]));
  window.addEventListener("message", (event) => {
    if (event.origin !== ORIGIN || !event.data || typeof event.data.type !== "string") return;
    if (event.data.type === "cine-toaster:assistant-ready") {
      ready = true;
      tellAssistant();
    } else if (event.data.type === "cine-toaster:highlight") {
      pointed = event.data.shot || "";
      point();
    } else if (event.data.type === "cine-toaster:navigate") {
      follow(event.data.where);
    }
  });
}
