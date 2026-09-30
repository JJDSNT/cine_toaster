# Cine Toaster — one command per thing someone needs on the first day.
#
# Everything here works from a fresh clone. `make` alone sets up and reports.

PYTHON ?= python3
VENV ?= .venv

# A production is never created inside the checkout (ADR 0001, CT-0007), so the
# demos land beside it. Override with: make demo DEMOS=~/somewhere
DEMOS ?= $(HOME)/cine-toaster-demos
RUN = $(VENV)/bin/python
TOAST = $(VENV)/bin/toast

.DEFAULT_GOAL := setup
.PHONY: ui ui-test setup environment submodules install install-media install-audio install-gpu install-voice install-agents test check demo doctor serve clean help voice build

help:
	@echo "make setup     install and report what works"
	@echo "make demo      create both demo productions in $$HOME/cine-toaster-demos"
	@echo "make build     speak the reel's narration and render it to mp4"
	@echo "make serve     open the control room on the reel"
	@echo "make check     continuity and schema findings for the demos"
	@echo "make test      the full suite"
	@echo "make ui        build the production canvas (needs Node 20+)"
	@echo "make doctor    what works on this machine, and how to fix what does not"

# ---- Setup ----

# An existing environment is not assumed to be usable. `uv venv` without
# --seed creates one with no pip, and every install into it then fails while
# looking like it worked.
environment:
	@if [ ! -x "$(RUN)" ]; then \
		if command -v uv >/dev/null 2>&1; then \
			echo "==> Creating the environment with uv"; \
			uv venv --seed --python 3.12 $(VENV); \
		else \
			echo "==> Creating the environment with venv"; \
			$(PYTHON) -m venv $(VENV); \
		fi; \
	fi
	@$(RUN) -m pip --version >/dev/null 2>&1 || { \
		echo "==> The environment has no pip; adding it"; \
		$(RUN) -m ensurepip --upgrade >/dev/null 2>&1 \
			|| { command -v uv >/dev/null 2>&1 && uv pip install --python $(RUN) pip >/dev/null; } \
			|| { echo "ERROR: could not add pip to $(VENV). Remove it and run make again."; exit 1; }; \
	}

# gl-transitions is a submodule: a clone without --recursive has an empty
# directory, and the catalog would silently lose its shader bank.
submodules:
	@if [ -d .git ] && command -v git >/dev/null 2>&1; then \
		git submodule update --init --quiet; \
	fi

install: environment submodules
	@echo "==> Installing Cine Toaster"
	@$(RUN) -m pip install --quiet --upgrade pip
	@$(RUN) -m pip install --quiet -e .

install-media: install
	@echo "==> Installing the media extras (drawing, grading, focus)"
	@$(RUN) -m pip install --quiet -e '.[media]'

install-audio: install
	@echo "==> Installing the audio extra (offline narration)"
	@$(RUN) -m pip install --quiet -e '.[audio]'

install-gpu: install
	@echo "==> Installing the gpu extra (transitions run their own shaders)"
	@$(RUN) -m pip install --quiet -e '.[gpu]'

# The directing assistant (ADR 0017, 0018): LangGraph over AG-UI. The model is
# the Claude Code CLI with your own login, so no key is needed.
install-agents: install
	@echo "==> Installing the agents extra (the assistant)"
	@$(RUN) -m pip install --quiet -e '.[agents]'

# Voice conversion (CT-0040) runs in its own environment: its engines pin
# their own numpy and torch. CPU is enough; nothing here needs a GPU.
install-voice:
	@echo "==> Creating .venv-voice (Chatterbox, Demucs, Resemblyzer; about 2 GB)"
	@uv venv --quiet --allow-existing --python 3.11 .venv-voice
	@VIRTUAL_ENV=.venv-voice uv pip install --quiet -r requirements-voice.txt --index-strategy unsafe-best-match
	@.venv-voice/bin/python -c "import chatterbox, demucs, resemblyzer" && echo "    voice conversion ready"

# The canvas is React (ADR 0015). Node is needed to build it, never to run
# Cine Toaster: the build lands in the package and the runtime serves it.
ui:
	@if command -v npm >/dev/null 2>&1; then \
		echo "==> Building the production canvas"; \
		cd frontend && SCARF_ANALYTICS=false npm ci --no-audit --no-fund --loglevel=error && npm run build --silent; \
	else \
		echo "Node is not installed: the canvas is skipped. Install Node 20+ and run make ui."; \
	fi

ui-test:
	@if command -v npm >/dev/null 2>&1 && [ -d frontend/node_modules ]; then \
		cd frontend && npm run typecheck --silent && npm test --silent; \
	else \
		echo "Skipping the canvas tests: run make ui first."; \
	fi

setup: install-media install-audio install-gpu ui
	@$(TOAST) doctor
	@echo "Next:  make demo    then    make serve"

# ---- Using it ----

demo: install
	@echo "==> Creating both demo productions in $(DEMOS)"
	@$(TOAST) demo "$(DEMOS)/the-last-signal" --template the-last-signal
	@$(TOAST) demo "$(DEMOS)/amiga-demo-reel" --template amiga-demo-reel
	@echo ""
	@$(TOAST) check "$(DEMOS)/the-last-signal" || true
	@$(TOAST) check "$(DEMOS)/amiga-demo-reel" || true
	@echo ""
	@echo "Both productions are in $(DEMOS). Open one with: make serve"

serve: install
	@$(TOAST) serve "$(DEMOS)/amiga-demo-reel"

check: install
	@$(TOAST) check "$(DEMOS)/the-last-signal"
	@$(TOAST) check "$(DEMOS)/amiga-demo-reel"

doctor: install
	@$(TOAST) doctor

voice: install-audio
	@$(TOAST) voice "$(DEMOS)/amiga-demo-reel"

build: install-media install-audio
	@$(TOAST) voice "$(DEMOS)/amiga-demo-reel"
	@$(TOAST) build "$(DEMOS)/amiga-demo-reel"

# ---- Development ----

test: install
	@PYTHONPATH=src $(RUN) -m unittest discover -s tests
	@$(MAKE) --no-print-directory ui-test

clean:
	@$(RUN) -c "import pathlib, shutil; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__') if '$(VENV)' not in str(p)]" 2>/dev/null || true
	@echo "Caches removed. The environment and $(DEMOS) are left alone."
