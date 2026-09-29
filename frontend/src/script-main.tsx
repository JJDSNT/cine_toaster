import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import "./script.css";
import { ScriptApp } from "./ScriptApp.tsx";

createRoot(document.getElementById("root")!).render(<StrictMode><ScriptApp /></StrictMode>);
