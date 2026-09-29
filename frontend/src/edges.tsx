import { BaseEdge, EdgeLabelRenderer, getBezierPath, getSmoothStepPath, type Edge, type EdgeProps } from "@xyflow/react";
import type { CutData } from "./types.ts";

export type CutEdge = Edge<CutData & Record<string, unknown>, "cut">;

export const CUT_NAMES: Record<string, string> = {
  hard: "Cut", match: "Match cut", action: "Cut on action", j: "J-cut",
  l: "L-cut", smash: "Smash cut", jump: "Jump cut", continuation: "Continuation",
};

// A cut is the edge between two shots: what kind it is, what it passes
// through, and whether the checks found anything wrong with it (SPEC-0007).
export function CutLine(props: EdgeProps<CutEdge>) {
  const { data, selected } = props;
  // A cut that wraps to the next line steps down under the cards instead of
  // cutting diagonally across them.
  const wraps = props.targetX < props.sourceX;
  const [path, labelX, labelY] = wraps
    ? getSmoothStepPath({ ...props, offset: 24, borderRadius: 12 })
    : getBezierPath(props);
  const severity = data?.severity || "";
  return (
    <>
      <BaseEdge path={path} className={`cut-line ${severity} ${data?.chain ? "chained" : ""} ${selected ? "selected" : ""}`} />
      <EdgeLabelRenderer>
        <div
          className={`cut-label ${severity} ${selected ? "selected" : ""}`}
          style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
        >
          <strong>{CUT_NAMES[data?.cut || "hard"] || data?.cut}</strong>
          {data?.transition && <small>{data.transition}</small>}
          {data?.findings.length ? <em>{data.findings.length}</em> : null}
        </div>
      </EdgeLabelRenderer>
    </>
  );
}

export const edgeTypes = { cut: CutLine };
