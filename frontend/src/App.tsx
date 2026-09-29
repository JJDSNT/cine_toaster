import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Background, Controls, ReactFlow, ReactFlowProvider,
  type Edge, type Node, type NodeMouseHandler, type EdgeMouseHandler,
} from "@xyflow/react";
import { layout } from "./layout.ts";
import { nodeTypes } from "./nodes.tsx";
import { CUT_NAMES, edgeTypes } from "./edges.tsx";
import type { GraphEdge, GraphNode, ProductionGraph } from "./types.ts";

type Selection = { kind: "node"; node: GraphNode } | { kind: "edge"; edge: GraphEdge } | null;

function toFlow(graph: ProductionGraph, showTakes: boolean): { nodes: Node[]; edges: Edge[] } {
  const visible = graph.nodes.filter((node) => showTakes || node.type !== "take");
  const positions = layout(visible, { takes: showTakes });
  const nodes: Node[] = visible.map((node) => ({
    id: node.id,
    type: node.type,
    position: positions.get(node.id) ?? { x: 0, y: 0 },
    data: node.data as unknown as Record<string, unknown>,
  }));
  const edges: Edge[] = graph.edges
    .filter((edge) => showTakes || edge.type !== "take")
    .map((edge) => {
      if (edge.type === "cut") {
        return { id: edge.id, source: edge.source, target: edge.target, type: "cut", data: edge.data as unknown as Record<string, unknown> };
      }
      if (edge.type === "take") {
        return { id: edge.id, source: edge.source, sourceHandle: "takes", target: edge.target,
                 className: edge.data.selected ? "take-line chosen" : "take-line" };
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

  const load = useCallback(() => {
    fetch("/api/graph")
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error(`HTTP ${response.status}`))))
      .then((value: ProductionGraph) => { setGraph(value); setError(""); })
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

  const flow = useMemo(() => (graph ? toFlow(graph, showTakes) : { nodes: [], edges: [] }), [graph, showTakes]);

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
        <label className="toggle"><input type="checkbox" checked={showTakes} onChange={(e) => setShowTakes(e.target.checked)} /> Takes</label>
      </header>
      {error && <p className="error">Could not read the production: {error}</p>}
      <main>
        <div className="canvas" data-testid="canvas">
          <ReactFlow
            nodes={flow.nodes}
            edges={flow.edges}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            nodesDraggable={false}
            nodesConnectable={false}
            edgesFocusable
            onNodeClick={onNodeClick}
            onEdgeClick={onEdgeClick}
            onPaneClick={() => setSelection(null)}
            fitView
            minZoom={0.2}
            proOptions={{ hideAttribution: false }}
          >
            <Background gap={24} />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
        <aside className="details"><Details selection={selection} /></aside>
      </main>
    </div>
  );
}

export function Root() {
  return <ReactFlowProvider><App /></ReactFlowProvider>;
}
