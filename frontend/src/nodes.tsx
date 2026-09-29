import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import type { SceneData, ShotData, TakeData } from "./types.ts";

export type SceneNode = Node<SceneData & Record<string, unknown>, "scene">;
export type ShotNode = Node<ShotData & Record<string, unknown>, "shot">;
export type TakeNode = Node<TakeData & Record<string, unknown>, "take">;

const LEVELS: Record<string, string> = {
  still: "Master still",
  take: "Selected take",
  blocking: "Blocking frame",
  none: "No picture yet",
};

export function SceneCard({ data, selected }: NodeProps<SceneNode>) {
  return (
    <div className={`card scene-card ${selected ? "selected" : ""}`}>
      <span className="eyebrow">{data.scene}</span>
      <strong>{data.title}</strong>
      {data.sequence && <small>{data.sequence}</small>}
      <span className={`pill status-${data.status}`}>{data.status.replace(/_/g, " ") || "—"}</span>
      {data.findings > 0 && <span className={`flag ${data.severity}`}>{data.findings} finding{data.findings > 1 ? "s" : ""}</span>}
    </div>
  );
}

export function ShotCard({ data, selected }: NodeProps<ShotNode>) {
  const picture = data.picture;
  return (
    <div className={`card shot-card ${selected ? "selected" : ""} ${data.severity}`}>
      <Handle type="target" position={Position.Left} />
      <div className="frame">
        {picture.image && <img src={picture.image} alt="" loading="lazy" />}
        {!picture.image && picture.video && <video src={`${picture.video}#t=0.1`} muted preload="metadata" />}
        {picture.level === "none" && <span className="no-picture">No picture yet</span>}
        <span className={`level level-${picture.level}`}>{LEVELS[picture.level]}</span>
      </div>
      <div className="shot-head">
        <strong>{data.shot}</strong>
        <span>{data.camera || "no camera"}</span>
        <span>{data.duration_seconds}s</span>
      </div>
      <p className="shot-label">{data.label}</p>
      <div className="shot-tags">
        {data.move && data.move !== "static" && <span className="tag move">{data.move}</span>}
        {data.walks && <span className="tag move">walk</span>}
        {data.speakers.map((who) => <span key={who} className="tag speaker">{who}</span>)}
        {data.takes > 0 && <span className="tag">{data.takes} take{data.takes > 1 ? "s" : ""}</span>}
        {data.findings > 0 && <span className={`flag ${data.severity}`}>{data.findings}</span>}
      </div>
      <Handle type="source" position={Position.Right} />
      <Handle type="source" position={Position.Bottom} id="takes" />
    </div>
  );
}

export function TakeCard({ data, selected }: NodeProps<TakeNode>) {
  return (
    <div className={`card take-card ${selected ? "selected" : ""} ${data.selected ? "chosen" : ""}`}>
      <Handle type="target" position={Position.Top} />
      <span className="take-mark">{data.selected ? "●" : "○"}</span>
      <span className="take-label">{data.label}</span>
      <small>{data.status.replace(/_/g, " ")}</small>
    </div>
  );
}

export const nodeTypes = { scene: SceneCard, shot: ShotCard, take: TakeCard };
