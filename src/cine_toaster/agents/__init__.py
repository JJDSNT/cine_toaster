"""The Agent Runtime's assistant (ADR 0017): a LangGraph agent served over AG-UI.

Optional (`pip install -e '.[agents]'`). It is a client of the runtime like any
interface: it reads the production through the runtime's HTTP API and changes
it only through `/api/commands`, as an agent actor, after the person confirms.
It never decides a human gate.
"""
