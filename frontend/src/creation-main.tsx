import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Creation } from "./Creation.tsx";
import "./preproduction.css";
import "./creation.css";

createRoot(document.getElementById("root")!).render(<StrictMode><Creation /></StrictMode>);
