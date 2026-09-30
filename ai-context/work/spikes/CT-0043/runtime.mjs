// The open path (CT-0033): browser -> this Copilot Runtime (Node) -> the Python AG-UI agent.
import { createServer } from "node:http";
import { HttpAgent } from "@ag-ui/client";
import { CopilotRuntime, InMemoryAgentRunner } from "@copilotkit/runtime/v2";
import { createCopilotNodeListener } from "@copilotkit/runtime/v2/node";

const runtime = new CopilotRuntime({
  agents: { director: new HttpAgent({ url: "http://127.0.0.1:8123/" }) },
  runner: new InMemoryAgentRunner(),
});
createServer(createCopilotNodeListener({ runtime, basePath: "/api/copilotkit" })).listen(4190, "127.0.0.1",
  () => console.log("runtime on 4190"));
