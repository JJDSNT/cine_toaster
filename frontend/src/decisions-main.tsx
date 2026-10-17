import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { DecisionInbox } from "./DecisionInbox.tsx";
import "./preproduction.css";
import "./creation.css";

createRoot(document.getElementById("root")!).render(<StrictMode><DecisionInbox /></StrictMode>);
