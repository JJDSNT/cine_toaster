// The Copilot Runtime: the open path between CopilotKit in the page and the
// Python assistant over AG-UI (ADR 0017, CT-0033). Built into one file
// (`npm run build`) that needs Node to run, never node_modules. The Python
// runtime starts and supervises it, and proxies /api/copilotkit to it, so the
// page talks to a single origin.
import { createServer } from "node:http";
import { HttpAgent } from "@ag-ui/client";
import { CopilotRuntime, InMemoryAgentRunner } from "@copilotkit/runtime/v2";
import { createCopilotNodeListener } from "@copilotkit/runtime/v2/node";

const port = Number(process.env.CINE_TOASTER_COPILOT_PORT || 8789);
const agentUrl = process.env.CINE_TOASTER_ASSISTANT_URL || "http://127.0.0.1:8788/";

const runtime = new CopilotRuntime({
  agents: { assistant: new HttpAgent({ url: agentUrl }) },
  runner: new InMemoryAgentRunner(),
});

// Measured in CT-0043: a dropped connection from the agent crashed the whole
// runtime. A failed turn is reported, and the runtime stays up.
process.on("uncaughtException", (error) => console.error("copilot runtime:", error.message));
process.on("unhandledRejection", (error) => console.error("copilot runtime:", String(error)));

createServer(createCopilotNodeListener({ runtime, basePath: "/api/copilotkit" }))
  .listen(port, "127.0.0.1", () => console.log(`copilot runtime on ${port}`));
