import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The build goes into the Python package, which serves it at /app/ (ADR 0015):
// the production canvas at /app/ and the screenplay editor at /app/script.html
// (ADR 0016). `npm run dev` proxies the control room's API, so run
// `toast serve` beside it.
const runtime = "http://127.0.0.1:8787";

export default defineConfig({
  base: "/app/",
  plugins: [react()],
  build: {
    outDir: "../src/cine_toaster/web_assets/app",
    emptyOutDir: true,
    rollupOptions: { input: { canvas: "index.html", script: "script.html" } },
  },
  server: { proxy: { "/api": runtime, "/media": runtime } },
});
