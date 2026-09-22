"""The one place an authored file's vocabulary meets the domain model.

A breakdown is written by people, in the language of the film's crew. The
domain model is the application's, and the application serves any film in any
language, so its vocabulary is English.

Cine Toaster's early productions were authored in Portuguese. When the export
step was removed and the production's own YAML became the native format
(ADR 0010), the film's language became the application's schema. The decision
was right and this was its cost.

English is the schema. The legacy names below are accepted so that a production
already in flight keeps loading, and for no other reason. They are a
compatibility map, not a second schema:

- nothing new is added here;
- a canonical name always wins over a legacy one;
- the table is deleted when the productions that need it have migrated.
"""

from __future__ import annotations

from typing import Any


#: Breakdown file names, canonical first.
SCENE_FILES: tuple[str, ...] = ("scene.yaml", "decupagem.yaml")

#: Project manifest file name.
PROJECT_FILE = "project.yaml"

#: Scene directory names under the project root, canonical first.
SCENE_DIRECTORIES: tuple[str, ...] = ("scenes", "cenas")

#: A scene's generated-media directory, canonical first.
WORK_DIRECTORIES: tuple[str, ...] = ("work", "trabalho")

#: Kept-for-comparison and rejected take directories, canonical first.
TAKES_DIRECTORIES: tuple[str, ...] = ("_takes", "_tomadas")
REJECTED_DIRECTORIES: tuple[str, ...] = ("_rejected", "_descartados")


#: canonical key -> legacy keys accepted in its place.
LEGACY_KEYS: dict[str, tuple[str, ...]] = {
    # Project manifest
    "title": ("titulo",),
    "format": ("formato",),
    "paths": ("caminhos",),
    "production": ("producao",),
    "sequences": ("sequencias",),
    "phases": ("fases",),
    # Manifest: paths
    "scenes": ("cenas",),
    "script": ("roteiro",),
    # Manifest: production
    "active_scene": ("cena_ativa",),
    "phase": ("fase",),
    # Manifest: a sequence
    "label": ("rotulo", "plano", "nome", "o"),
    "act": ("ato",),
    "render": ("montagem",),
    "summary": ("resumo", "situacao"),
    # Scene
    "scene": ("cena",),
    "order": ("ordem",),
    "sequence": ("sequencia",),
    "variant": ("variante",),
    "direction": ("direcao",),
    "step": ("etapa",),
    "steps": ("etapas",),
    "blockers": ("impedimentos",),
    "decisions": ("decisoes",),
    "geography": ("geografia",),
    "shots": ("planos",),
    # Scene: a decision
    "question": ("pergunta",),
    "proposal": ("proposta",),
    "answer": ("resposta",),
    # Shot
    "kind": ("tipo",),
    "from": ("usa", "usa_de", "usa_arquivo", "usa_ultimo_de", "reusa", "deriva", "ref"),
    "text": ("texto_tela", "textos"),
    "ops": ("operacoes",),
    "sound": ("som",),
    "notes": ("nota_montagem", "nota_producao"),
    "lines": ("falas",),
    "transition": ("transicao",),
    "engine": ("motor",),
    "reason": ("razao",),
    "who": ("quem",),
    "delivery": ("como",),
    "voice": ("voz",),
    "mix": ("montagem",),
    "subject": ("sujeito",),
    "looks_at": ("olha_para",),
    "action": ("atuacao",),
    "out_of_cut": ("fora_do_corte",),
    "duration": ("dur",),
    # Geography
    "room": ("sala",),
    "subjects": ("pessoas",),
    "eye_height": ("altura_olhos",),
    "height": ("altura",),
    "target": ("mira",),
    "lens_mm": ("lente",),
    "axis": ("eixo",),
}


#: Where a shot's frames come from (SPEC-0004).
SOURCES: frozenset[str] = frozenset({"generated", "captured", "archival", "composed"})

#: Legacy `tipo` values, mapped to the source they always meant.
KIND_SOURCES: dict[str, str] = {
    "black": "composed",
    "white": "composed",
    "title_card": "composed",
    "image": "generated",
    "still": "generated",
    "ltx": "generated",
    "clip": "archival",
    "trecho": "archival",
}

#: Engines that compose frames rather than generate or capture them.
COMPOSED_ENGINES: frozenset[str] = frozenset({"solid", "title", "text", "rig", "remotion", "hyperframes"})

#: Legacy `tipo` values, mapped to the engine they always meant.
KIND_ENGINES: dict[str, str] = {
    "black": "solid",
    "white": "solid",
    "title_card": "title",
    "ltx": "ltx",
}

#: Shot fields the typed core understands (SPEC-0004). Their legacy names are
#: added below, so a breakdown in the old vocabulary is not reported as unknown.
CORE_SHOT_FIELDS: frozenset[str] = frozenset(
    {
        "n",
        "kind",
        "label",
        "duration",
        "camera",
        "camera_id",
        "subject",
        "looks_at",
        "action",
        "out_of_cut",
        "source",
        "engine",
        "from",
        "variant",
        "text",
        "ops",
        "sound",
        "notes",
        "lines",
        "transition",
        "look",
    }
)


def _with_legacy(names: frozenset[str]) -> frozenset[str]:
    known = set(names)
    for canonical in names:
        known.update(LEGACY_KEYS.get(canonical, ()))
    return frozenset(known)


#: Shot kinds that stand in for a frame instead of naming generated footage.
LEGACY_SHOT_KINDS: dict[str, str] = {
    "preto": "black",
    "branco": "white",
    "cartela": "title_card",
    "imagem": "image",
}

#: Shot kinds that carry no take because the frame is drawn, not generated.
GENERATED_NOTHING: frozenset[str] = frozenset({"black", "white", "title_card", "image"})

#: Scene statuses that count as finished.
LEGACY_STATUSES: dict[str, str] = {"aprovado": "approved"}


def field(document: dict[str, Any], canonical: str, default: Any = None) -> Any:
    """Read ``canonical`` from ``document``, falling back to its legacy names.

    A canonical name always wins, so a file being migrated key by key stays
    readable while it is half-translated.
    """

    if canonical in document:
        value = document[canonical]
        if value is not None:
            return value
    for legacy in LEGACY_KEYS.get(canonical, ()):
        if legacy in document:
            value = document[legacy]
            if value is not None:
                return value
    return default


def text(document: dict[str, Any], canonical: str, default: str = "") -> str:
    value = field(document, canonical)
    return default if value is None else str(value)


def shot_kind(raw: Any) -> str:
    """Normalize a shot kind to the domain vocabulary."""

    value = "" if raw is None else str(raw).strip().lower()
    return LEGACY_SHOT_KINDS.get(value, value)


def status(raw: Any) -> str:
    """Normalize an authored status to the domain vocabulary."""

    value = "" if raw is None else str(raw).strip().lower()
    return LEGACY_STATUSES.get(value, value)


#: Every shot field name the typed core accepts, canonical and legacy.
KNOWN_SHOT_FIELDS: frozenset[str] = _with_legacy(CORE_SHOT_FIELDS)
