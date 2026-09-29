import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { EditorState } from "@codemirror/state";
import { EditorView, keymap } from "@codemirror/view";
import { basicSetup } from "codemirror";
import { fountainSupport } from "./fountainLanguage.ts";
import { normalizeHeading, outline, type OutlineEntry } from "./fountain.ts";

// The screenplay editor (ADR 0016). It sends back exactly the text written
// here; the runtime writes it byte for byte, or refuses when the file changed
// since it was opened. Generated screenplays open read only.

interface ScriptFile { path: string; text: string; revision: string; line_endings: string }
interface Opened { files: ScriptFile[]; editable: boolean; reason: string; problem: string }
interface Finding { code: string; severity: string; message: string; scene_id: string; shots?: string[] }
interface Impact { new: Finding[]; cleared: Finding[]; counts: Record<string, number> }
interface SceneLink { id: string; title: string; heading: string; occurrence: number }

type Status = { kind: "idle" } | { kind: "saving" } | { kind: "saved"; at: string } | { kind: "conflict"; message: string } | { kind: "error"; message: string };

const theme = EditorView.theme({
  "&": { height: "100%", backgroundColor: "#0c0e0f", color: "#c9d0d3", fontSize: "14px" },
  ".cm-content": { fontFamily: "'Courier Prime', 'Courier New', ui-monospace, monospace", padding: "24px 0", maxWidth: "72ch", margin: "0 auto" },
  ".cm-gutters": { backgroundColor: "#0c0e0f", color: "#3a4247", border: "none" },
  ".cm-activeLine": { backgroundColor: "#ffffff08" },
  ".cm-activeLineGutter": { backgroundColor: "#ffffff08" },
  "&.cm-focused .cm-cursor": { borderLeftColor: "#ff6a3d" },
  ".cm-selectionBackground, &.cm-focused .cm-selectionBackground": { backgroundColor: "#ff6a3d33 !important" },
}, { dark: true });

export function ScriptApp() {
  const [opened, setOpened] = useState<Opened | null>(null);
  const [error, setError] = useState("");
  const [current, setCurrent] = useState(0);
  const [texts, setTexts] = useState<Record<string, string>>({});
  const [revisions, setRevisions] = useState<Record<string, string>>({});
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [impact, setImpact] = useState<Impact | null>(null);
  const [links, setLinks] = useState<SceneLink[]>([]);
  // Bumped only when files are (re)loaded from disk: saving must not reset
  // the cursor, the scroll or the undo history.
  const [loaded, setLoaded] = useState(0);
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView | null>(null);
  const saveRef = useRef<() => void>(() => {});

  const load = useCallback(() => {
    fetch("/api/screenplay")
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error(`HTTP ${response.status}`))))
      .then((value: Opened) => {
        setOpened(value);
        setTexts(Object.fromEntries(value.files.map((file) => [file.path, file.text])));
        setRevisions(Object.fromEntries(value.files.map((file) => [file.path, file.revision])));
        setStatus({ kind: "idle" });
        setLoaded((count) => count + 1);
      })
      .catch((reason: Error) => setError(reason.message));
    fetch("/api/production")
      .then((response) => response.json())
      .then((production: { scenes: { id: string; title: string; script: { heading: string; occurrence: number } | null }[] }) =>
        setLinks(production.scenes.filter((scene) => scene.script).map((scene) => ({
          id: scene.id, title: scene.title, heading: normalizeHeading(scene.script!.heading), occurrence: scene.script!.occurrence || 1,
        }))))
      .catch(() => setLinks([]));
  }, []);
  useEffect(load, [load]);

  const file = opened?.files[current];
  const dirty = useMemo(() => (opened?.files ?? []).filter((item) => texts[item.path] !== item.text).map((item) => item.path), [opened, texts]);

  // One CodeMirror view; switching file swaps its document.
  useEffect(() => {
    if (!host.current || !opened || !file) return;
    const state = EditorState.create({
      doc: texts[file.path] ?? file.text,
      extensions: [
        basicSetup,
        fountainSupport,
        theme,
        EditorView.lineWrapping,
        EditorState.readOnly.of(!opened.editable),
        EditorView.editable.of(opened.editable),
        keymap.of([{ key: "Mod-s", preventDefault: true, run: () => { saveRef.current(); return true; } }]),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) {
            const text = update.state.doc.toString();
            setTexts((previous) => ({ ...previous, [file.path]: text }));
          }
        }),
      ],
    });
    if (view.current) view.current.setState(state);
    else view.current = new EditorView({ state, parent: host.current });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded, file?.path]);

  useEffect(() => () => view.current?.destroy(), []);

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (dirty.length) event.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty.length]);

  const save = useCallback(async () => {
    if (!opened?.editable || !file) return;
    setStatus({ kind: "saving" });
    const response = await fetch("/api/screenplay", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: file.path, text: texts[file.path], revision: revisions[file.path], actor: { id: "screenplay-editor" } }),
    });
    const payload = await response.json();
    if (!response.ok) {
      const message = payload.error?.message ?? `HTTP ${response.status}`;
      setStatus(payload.error?.code === "revision_conflict" ? { kind: "conflict", message } : { kind: "error", message });
      return;
    }
    setRevisions((previous) => ({ ...previous, [file.path]: payload.revision }));
    setOpened((previous) => previous && ({
      ...previous,
      files: previous.files.map((item) => (item.path === file.path ? { ...item, text: texts[file.path], revision: payload.revision } : item)),
    }));
    setImpact(payload.impact);
    setStatus({ kind: "saved", at: new Date().toLocaleTimeString() });
  }, [opened, file, texts, revisions]);
  saveRef.current = save;

  // Occurrences continue across files, as the runtime reads them (one screenplay).
  const entries = useMemo(() => {
    if (!opened) return [] as OutlineEntry[];
    const seen = new Map<string, number>();
    let mine: OutlineEntry[] = [];
    opened.files.forEach((item, index) => {
      const found = outline(texts[item.path] ?? item.text, seen);
      if (index === current) mine = found;
    });
    return mine;
  }, [opened, texts, current]);

  const jump = (line: number) => {
    const editor = view.current;
    if (!editor) return;
    const position = editor.state.doc.line(Math.min(line, editor.state.doc.lines)).from;
    editor.dispatch({ selection: { anchor: position }, effects: EditorView.scrollIntoView(position, { y: "start" }) });
    editor.focus();
  };

  if (error) return <p className="error">Could not open the screenplay: {error}</p>;
  if (!opened) return <p className="hint pad">Opening the screenplay…</p>;
  if (!opened.files.length) {
    return (
      <div className="shell"><header><a className="back" href="/">← Control room</a><h1>Screenplay</h1></header>
        <p className="error pad">{opened.problem || "This production has no screenplay."}</p></div>
    );
  }

  return (
    <div className="shell script-shell">
      <header>
        <a className="back" href="/">← Control room</a>
        <div>
          <span className="eyebrow">Screenplay{opened.editable ? "" : " · read only"}</span>
          <h1>{file?.path}</h1>
        </div>
        <span className={`save-status ${status.kind}`}>
          {status.kind === "saving" && "Saving…"}
          {status.kind === "saved" && `Saved ${status.at}`}
          {status.kind === "idle" && (file && dirty.includes(file.path) ? "Unsaved changes" : "")}
          {status.kind === "error" && status.message}
        </span>
        {opened.editable && (
          <button type="button" className="primary" onClick={save} disabled={!file || !dirty.includes(file.path) || status.kind === "saving"}>
            Save
          </button>
        )}
      </header>
      {!opened.editable && <p className="banner readonly">{opened.reason}</p>}
      {status.kind === "conflict" && (
        <p className="banner conflict">
          {status.message}{" "}
          <button type="button" onClick={() => { if (!dirty.length || confirm("Discard your unsaved changes and reload?")) load(); }}>Reload</button>
        </p>
      )}
      {opened.files.length > 1 && (
        <nav className="file-tabs">
          {opened.files.map((item, index) => (
            <button key={item.path} type="button" className={index === current ? "active" : ""} onClick={() => setCurrent(index)}>
              {item.path.split("/").pop()}{dirty.includes(item.path) ? " •" : ""}
            </button>
          ))}
        </nav>
      )}
      <main className={`script-main ${opened.editable ? "" : "reading"}`}>
        <aside className="outline">
          <span className="eyebrow">Scenes</span>
          {entries.map((entry) => {
            const linked = links.filter((link) => link.heading === normalizeHeading(entry.text) && link.occurrence === entry.occurrence);
            return (
              <button key={`${entry.line}`} type="button" className={`outline-${entry.kind}`} onClick={() => jump(entry.line)}>
                <span>{entry.text}</span>
                {linked.map((link) => <em key={link.id} title={link.title}>{link.id}</em>)}
              </button>
            );
          })}
        </aside>
        <div className="editor" ref={host} />
        {opened.editable && <aside className="impact">
          <span className="eyebrow">What the last save did to the film</span>
          {!impact && <p className="hint">Saving checks the film's links to this text: a shot's quoted line that no longer exists, a line that drifted, dialogue no shot covers.</p>}
          {impact && !impact.new.length && !impact.cleared.length && <p className="hint">No shot's link to the screenplay changed.</p>}
          {impact?.new.map((finding, index) => (
            <p key={`n${index}`} className={`finding ${finding.severity}`}><strong>{finding.scene_id}</strong> {finding.message}</p>
          ))}
          {impact && impact.cleared.length > 0 && <p className="hint">{impact.cleared.length} earlier finding(s) cleared.</p>}
        </aside>}
      </main>
    </div>
  );
}
