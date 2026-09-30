import { defineConfig } from "vite";

// The Copilot Runtime as one self-contained Node module.
export default defineConfig({
  build: {
    ssr: "copilot-runtime.ts",
    outDir: "../src/cine_toaster/web_assets/copilot",
    emptyOutDir: true,
    target: "node20",
    rollupOptions: { output: { entryFileNames: "copilot-runtime.mjs", inlineDynamicImports: true } },
  },
  ssr: { noExternal: true, target: "node" },
});
