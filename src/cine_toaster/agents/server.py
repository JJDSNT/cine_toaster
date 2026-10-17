"""The assistant served over AG-UI, in a thread of the runtime process (ADR 0017).

`toast serve --assistant` starts it beside the control room. Conversations are
kept in memory only: they are disposable operational state, and a restart
forgets them, never the film.
"""

from __future__ import annotations

import threading

from .assistant import build
from .catalog import role_models
from .models import model_from_env
from .runtime_client import RuntimeClient


def app(runtime_url: str, model=None):
    from ag_ui_langgraph import LangGraphAgent, add_langgraph_fastapi_endpoint
    from fastapi import FastAPI
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    # The page's context arrives as AG-UI objects and is checkpointed with the
    # turn; name the type, rather than rely on a default LangGraph will close.
    serde = JsonPlusSerializer(allowed_msgpack_modules=[("ag_ui._generated.models", "Context")])
    model = model if model is not None else model_from_env()
    # Every role uses the model the host was given, unless the person bound a role to another (ADR 0034).
    graph = build(model, RuntimeClient(runtime_url), MemorySaver(serde=serde), models=role_models(model))
    application = FastAPI(title="Cine Toaster assistant")
    add_langgraph_fastapi_endpoint(application, LangGraphAgent(name="assistant", graph=graph), "/")
    return application


def serve_in_thread(runtime_url: str, port: int, host: str = "127.0.0.1", model=None) -> threading.Thread:
    import uvicorn

    server = uvicorn.Server(uvicorn.Config(app(runtime_url, model), host=host, port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, name="assistant", daemon=True)
    thread.start()
    return thread
