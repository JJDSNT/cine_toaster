import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The build goes into the Python package, which serves it at /canvas/ (ADR 0015).
// `npm run dev` proxies the control room's API, so run `toast serve` beside it.
const runtime = "http://127.0.0.1:8787";

export default defineConfig({
  base: "/canvas/",
  plugins: [react()],
  build: {
    outDir: "../src/cine_toaster/web_assets/canvas",
    emptyOutDir: true,
  },
  server: { proxy: { "/api": runtime, "/media": runtime } },
});
