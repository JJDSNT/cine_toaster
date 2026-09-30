import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import {
  Background, Controls, ReactFlow, ReactFlowProvider,
  type Edge, type Node, type NodeMouseHandler, type EdgeMouseHandler,
} from "@xyflow/react";
import { layout } from "./layout.ts";
import { nodeTypes } from "./nodes.tsx";
import { CUT_NAMES, edgeTypes } from "./edges.tsx";
import type { GraphEdge, GraphNode, ProductionGraph } from "./types.ts";

// The assistant is its own chunk, fetched only when the runtime has it on (ADR 0018).
const Assistant = lazy(() => import("./Assistant.tsx"));
import { addressOf, type Navigation } from "./navigation.ts";

type Selection = { kind: "node"; node: GraphNode } | { kind: "edge"; edge: GraphEdge } | null;

/** The films this view shows: everything, one sequence, or one scene. */
type Focus = { kind: "all" } | { kind: "sequence"; id: string } | { kind: "scene"; id: string };

const LARGE = 60;

function scenesIn(graph: ProductionGraph, focus: Focus): Set<string> | null {
  if (focus.kind === "all") return null;
  if (focus.kind === "scene") return new Set([focus.id]);
  return new Set(graph.production.sequences.find((item) => item.id === focus.id)?.scenes ?? []);
}

/** A large film opens on the sequence being worked on, not on everything at once. */
function initialFocus(graph: ProductionGraph): Focus {
  const shots = graph.nodes.filter((node) => node.type === "shot").length;
  if (shots <= LARGE) return { kind: "all" };
  const active = graph.production.active_scene;
  const sequence = graph.production.sequences.find((item) => item.scenes.includes(active));
  if (sequence) return { kind: "sequence", id: sequence.id };
  const first = graph.nodes.find((node) => node.type === "scene");
  return first ? { kind: "scene", id: first.scene } : { kind: "all" };
}

function toFlow(graph: ProductionGraph, showTakes: boolean, focus: Focus): { nodes: Node[]; edges: Edge[] } {
  const only = scenesIn(graph, focus);
  const visible = graph.nodes.filter((node) => (showTakes || node.type !== "take") && (!only || only.has(node.scene)));
  const shown = new Set(visible.map((node) => node.id));
  const positions = layout(visible, { takes: showTakes });
  const nodes: Node[] = visible.map((node) => ({
    id: node.id,
    type: node.type,
    position: positions.get(node.id) ?? { x: 0, y: 0 },
    data: node.data as unknown as Record<string, unknown>,
  }));
  const edges: Edge[] = graph.edges
    .filter((edge) => (showTakes || edge.type !== "take") && shown.has(edge.source) && shown.has(edge.target))
    .map((edge) => {
      if (edge.type === "cut") {
        return { id: edge.id, source: edge.source, target: edge.target, type: "cut", data: edge.data as unknown as Record<string, unknown> };
      }
      if (edge.type === "take") {
        return { id: edge.id, source: edge.source, sourceHandle: "takes", target: edge.target,
                 className: edge.data.selected ? "take-line chosen" : "take-line" };
      }
      if (edge.type === "run") {
        return { id: edge.id, source: edge.source, target: edge.target, type: "smoothstep",
                 className: `run-line run-${edge.data.state}`, animated: edge.data.state === "running", selectable: false };
      }
      return { id: edge.id, source: edge.source, target: edge.target, type: "smoothstep", className: "scene-line",
               label: "next scene", selectable: false };
    });
  return { nodes, edges };
}

function Details({ selection }: { selection: Selection }) {
  if (!selection) {
    return <p className="hint">Select a card or a cut to see its record. The canvas only reads the production: change it in the control room, and this view follows.</p>;
  }
  if (selection.kind === "edge") {
    const edge = selection.edge;
    if (edge.type !== "cut") return null;
    const [, scene, pair] = edge.id.match(/^cut:([^/]+)\/(.+)$/) ?? [];
    return (
      <div>
        <span className="eyebrow">Cut · {scene}</span>
        <h2>{pair?.replace("-", " → ")}</h2>
        <dl>
          <dt>Type</dt><dd>{CUT_NAMES[edge.data.cut] || edge.data.cut}</dd>
          {edge.data.chain && (<><dt>Chain</dt><dd>opens on the previous last frame</dd></>)}
          {edge.data.transition && (<><dt>Transition</dt><dd>{edge.data.transition}</dd></>)}
          {edge.data.reason && (<><dt>Why</dt><dd>{edge.data.reason}</dd></>)}
        </dl>
        {edge.data.findings.map((code) => <p key={code} className={`finding ${edge.data.severity}`}>{code}</p>)}
        <a href={`/?view=cut`}>Open the Cut room</a>
      </div>
    );
  }
  const node = selection.node;
  if (node.type === "scene") {
    return (
      <div>
        <span className="eyebrow">Scene · {node.data.scene}</span>
        <h2>{node.data.title}</h2>
        <dl><dt>Sequence</dt><dd>{node.data.sequence || "—"}</dd><dt>Status</dt><dd>{node.data.status}</dd><dt>Findings</dt><dd>{node.data.findings}</dd></dl>
        <a href={`/?scene=${encodeURIComponent(node.data.scene)}`}>Open the scene</a>
      </div>
    );
  }
  if (node.type === "run") {
    const d = node.data;
    return (
      <div>
        <span className="eyebrow">Workflow · {d.scene} block {d.block}</span>
        <h2>{d.state}</h2>
        <ol className="run-steps">{d.steps.map((step, index) => <li key={index}>{step.label}: {step.state}</li>)}</ol>
        {d.waiting && <p className="finding warning">Waiting for you: {d.waiting}</p>}
        <a href={`/?scene=${encodeURIComponent(d.scene)}`}>{d.waiting ? "Decide in the scene room" : "Open the scene"}</a>
      </div>
    );
  }
  if (node.type === "shot") {
    const d = node.data;
    return (
      <div>
        <span className="eyebrow">Shot · {d.scene}</span>
        <h2>{d.shot}</h2>
        <p>{d.label}</p>
        <dl>
          <dt>Camera</dt><dd>{d.camera || "—"}</dd>
          <dt>Duration</dt><dd>{d.duration_seconds} s</dd>
          <dt>Move</dt><dd>{d.move || "—"}{d.walks ? " · subjects walk" : ""}</dd>
          <dt>Speakers</dt><dd>{d.speakers.join(", ") || "—"}</dd>
          <dt>Picture</dt><dd>{d.picture.level}</dd>
          <dt>Selected take</dt><dd>{d.selected_take || "—"}</dd>
        </dl>
        <a href={`/?scene=${encodeURIComponent(d.scene)}&shot=${encodeURIComponent(d.shot)}`}>Compare takes</a>
      </div>
    );
  }
  const d = node.data;
  return (
    <div>
      <span className="eyebrow">Take · {d.scene} {d.shot}</span>
      <h2>{d.label}</h2>
      {d.media && <video src={d.media} controls muted playsInline />}
      <dl><dt>Status</dt><dd>{d.status}</dd><dt>Selected</dt><dd>{d.selected ? "yes" : "no"}</dd></dl>
      <a href={`/?scene=${encodeURIComponent(d.scene)}&shot=${encodeURIComponent(d.shot)}`}>Compare takes</a>
    </div>
  );
}

export function App() {
  const [graph, setGraph] = useState<ProductionGraph | null>(null);
  const [error, setError] = useState("");
  const [showTakes, setShowTakes] = useState(true);
  const [selection, setSelection] = useState<Selection>(null);
  const [focus, setFocus] = useState<Focus | null>(null);
  const [assistantOn, setAssistantOn] = useState(false);
  const [talking, setTalking] = useState(false);
  const [highlight, setHighlight] = useState("");

  useEffect(() => {
    fetch("/api/copilotkit/info").then((response) => setAssistantOn(response.ok)).catch(() => setAssistantOn(false));
  }, []);

  const load = useCallback(() => {
    fetch("/api/graph")
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error(`HTTP ${response.status}`))))
      .then((value: ProductionGraph) => {
        setGraph(value);
        setFocus((current) => current ?? initialFocus(value));
        setError("");
      })
      .catch((reason: Error) => setError(reason.message));
  }, []);

  useEffect(() => {
    load();
    // Committed changes arrive as events; job progress does not change the film.
    const source = new EventSource("/api/events/stream");
    source.onmessage = (message) => {
      try {
        const event = JSON.parse(message.data) as { type?: string };
        if (event.type?.startsWith("job.") && event.type !== "job.adopted") return;
      } catch { return; }
      load();
    };
    return () => source.close();
  }, [load]);

  const flow = useMemo(
    () => (graph && focus ? toFlow(graph, showTakes, focus) : { nodes: [], edges: [] }),
    [graph, showTakes, focus],
  );
  // What the person is looking at, for the assistant: the room, the scene, the selection.
  const seen = useMemo(() => {
    const selectedScene = selection?.kind === "node" ? selection.node.scene : "";
    const scene = focus?.kind === "scene" ? focus.id : selectedScene || graph?.production.active_scene || "";
    let selected = "";
    if (selection?.kind === "node") {
      const d = selection.node.data as unknown as Record<string, unknown>;
      selected = `${selection.node.type} ${[d.shot, d.take, d.run, d.title].filter(Boolean).join(" ")} in ${selection.node.scene}`;
      if (selection.node.type === "shot") selected += `: ${String(d.label ?? "")}`;
    } else if (selection?.kind === "edge") {
      selected = `cut ${selection.edge.id.replace(/^cut:/, "")}`;
    }
    const focusText = !focus || focus.kind === "all" ? "the whole film" : `${focus.kind} ${focus.id}`;
    return { room: "production canvas", scene, focus: focusText, selected };
  }, [selection, focus, graph]);
  // The assistant may move the screen: here on the canvas, or out to a room.
  const navigate = useCallback((where: Navigation) => {
    if (where.room === "canvas") {
      if (where.scene) setFocus({ kind: "scene", id: where.scene });
      return;
    }
    window.location.href = addressOf(where);
  }, []);
  const shown = useMemo(() => {
    if (!highlight) return flow.nodes;
    const target = `shot:${seen.scene}/${highlight}`;
    return flow.nodes.map((node) => (node.id === target ? { ...node, className: "assistant-highlight" } : node));
  }, [flow.nodes, highlight, seen.scene]);
  // Open on the first scene in view, readable, rather than shrinking a whole
  // sequence until nothing on it can be read.
  const firstScene = useMemo(() => {
    const scene = flow.nodes.find((node) => node.type === "scene");
    if (!scene) return undefined;
    const sceneId = (scene.data as { scene: string }).scene;
    return flow.nodes
      .filter((node) => (node.data as { scene?: string }).scene === sceneId && node.type !== "take")
      .map((node) => ({ id: node.id }));
  }, [flow.nodes]);
  const focusValue = !focus || focus.kind === "all" ? "all" : `${focus.kind}:${focus.id}`;
  const chooseFocus = (value: string) => {
    const [kind, ...rest] = value.split(":");
    setFocus(kind === "all" ? { kind: "all" } : { kind: kind as "sequence" | "scene", id: rest.join(":") });
    setSelection(null);
  };

  const onNodeClick: NodeMouseHandler = (_, node) => {
    const found = graph?.nodes.find((item) => item.id === node.id);
    setSelection(found ? { kind: "node", node: found } : null);
  };
  const onEdgeClick: EdgeMouseHandler = (_, edge) => {
    const found = graph?.edges.find((item) => item.id === edge.id);
    setSelection(found ? { kind: "edge", edge: found } : null);
  };

  return (
    <div className="shell">
      <header>
        <a className="back" href="/">← Control room</a>
        <div>
          <span className="eyebrow">Production canvas · read only</span>
          <h1>{graph?.production.title ?? "…"}</h1>
        </div>
        {graph && (
          <select className="focus" value={focusValue} onChange={(e) => chooseFocus(e.target.value)} aria-label="Show">
            <option value="all">Whole film · {graph.nodes.filter((n) => n.type === "shot").length} shots</option>
            {graph.production.sequences.length > 0 && (
              <optgroup label="Sequence">
                {graph.production.sequences.map((item) => <option key={item.id} value={`sequence:${item.id}`}>{item.label}</option>)}
              </optgroup>
            )}
            <optgroup label="Scene">
              {graph.nodes.filter((n) => n.type === "scene").map((n) => (
                <option key={n.id} value={`scene:${n.scene}`}>{n.scene} · {n.type === "scene" ? n.data.title : ""}</option>
              ))}
            </optgroup>
          </select>
        )}
        <label className="toggle"><input type="checkbox" checked={showTakes} onChange={(e) => setShowTakes(e.target.checked)} /> Takes</label>
        {assistantOn && (
          <button type="button" className={`toggle assistant-toggle ${talking ? "on" : ""}`} onClick={() => setTalking((value) => !value)}>
            Assistant
          </button>
        )}
      </header>
      {error && <p className="error">Could not read the production: {error}</p>}
      <main>
        <div className="canvas" data-testid="canvas">
          <ReactFlow
            nodes={shown}
            edges={flow.edges}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            nodesDraggable={false}
            nodesConnectable={false}
            edgesFocusable
            onNodeClick={onNodeClick}
            onEdgeClick={onEdgeClick}
            onPaneClick={() => setSelection(null)}
            key={focusValue}
            fitView
            fitViewOptions={{ maxZoom: 1, minZoom: 0.3, nodes: firstScene }}
            onlyRenderVisibleElements
            minZoom={0.05}
            proOptions={{ hideAttribution: false }}
          >
            <Background gap={24} />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
        <aside className="details">
          <Details selection={selection} />
          {assistantOn && talking && (
            <div className="assistant dark" data-testid="assistant">
              <Suspense fallback={<p className="hint">Opening the assistant…</p>}>
                <Assistant seen={seen} onHighlight={setHighlight} onNavigate={navigate} />
              </Suspense>
            </div>
          )}
        </aside>
      </main>
    </div>
  );
}

export function Root() {
  return <ReactFlowProvider><App /></ReactFlowProvider>;
}
