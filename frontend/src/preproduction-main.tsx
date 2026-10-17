import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Preproduction } from "./Preproduction.tsx";
import { ScreenplayCandidate } from "./ScreenplayCandidate.tsx";
import "./preproduction.css";

const draft = new URLSearchParams(window.location.search).get("draft");
createRoot(document.getElementById("root")!).render(<StrictMode>{draft ? <ScreenplayCandidate id={draft} /> : <Preproduction />}</StrictMode>);
