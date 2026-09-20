from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .geometry import CHECK_CODES


BUILTIN_KNOWLEDGE = Path(__file__).with_name("knowledge")
FRONTMATTER_FENCE = "+++"

PRACTICE_STATUSES = {"measured", "suspected", "convention", "refuted"}
CLAIM_STATUSES = {"measured", "suspected", "refuted", "unmeasured"}


def _roots(project_root: Path | None = None) -> list[tuple[str, Path]]:
    """Built-in, shared, then project knowledge, in increasing specificity.

    Same layering as the transition library: a team can share measured facts
    across productions, and a production can override or add its own without
    modifying the application.
    """

    roots: list[tuple[str, Path]] = [("built-in", BUILTIN_KNOWLEDGE)]
    configured = os.environ.get("CINE_TOASTER_KNOWLEDGE_PATH", "")
    for position, raw_path in enumerate(filter(None, configured.split(os.pathsep)), 1):
        roots.append((f"shared-{position}", Path(raw_path).expanduser()))
    if project_root is not None:
        roots.append(("project", project_root.expanduser().resolve() / "knowledge"))
    return roots


def parse_frontmatter(text: str, path: Path) -> tuple[dict[str, Any], str]:
    """Split a `+++` TOML header from the prose that follows it.

    Structured fields have to be machine-readable so the tool can report what it
    enforces; the reasoning has to stay prose so a person will actually write it.
    """

    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_FENCE:
        raise ValidationError(f"{path} must start with a {FRONTMATTER_FENCE} header")
    try:
        closing = next(
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.strip() == FRONTMATTER_FENCE
        )
    except StopIteration:
        raise ValidationError(f"{path} has no closing {FRONTMATTER_FENCE}") from None

    try:
        header = tomllib.loads("\n".join(lines[1:closing]))
    except tomllib.TOMLDecodeError as error:
        raise ValidationError(f"Invalid TOML header in {path}: {error}") from error
    return header, "\n".join(lines[closing + 1 :]).strip()


@dataclass(frozen=True, slots=True)
class Practice:
    """One thing the production learned, and whether software enforces it.

    The point of the record is not the rule; a skill document already states
    rules. The point is `enforced_by`: it makes visible which knowledge a
    machine now checks and which still depends on a person remembering at the
    right moment.
    """

    id: str
    title: str
    domain: str
    status: str
    body: str
    origin: str
    path: Path
    learned_on: str = ""
    enforced_by: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    cost: str = ""
    supersedes: str = ""

    @property
    def enforced(self) -> bool:
        return bool(self.enforced_by) and self.status != "refuted"

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "domain": self.domain,
            "status": self.status,
            "learned_on": self.learned_on,
            "enforced_by": list(self.enforced_by),
            "enforced": self.enforced,
            "evidence": list(self.evidence),
            "cost": self.cost,
            "supersedes": self.supersedes,
            "origin": self.origin,
            "body": self.body,
        }


@dataclass(frozen=True, slots=True)
class Claim:
    """One measured fact about how a provider behaves."""

    id: str
    claim: str
    status: str
    measured_on: str = ""
    evidence: tuple[str, ...] = ()
    impact: str = "medium"
    workaround: str = ""

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "claim": self.claim,
            "status": self.status,
            "measured_on": self.measured_on,
            "evidence": list(self.evidence),
            "impact": self.impact,
            "workaround": self.workaround,
        }


@dataclass(frozen=True, slots=True)
class ProviderProfile:
    """What a specific generator does and does not obey, with dates.

    A capability profile is not documentation. It is data a generation adapter
    reads, and it carries measurement dates so a claim about a model version can
    be re-tested instead of quietly ageing into folklore.
    """

    id: str
    title: str
    kind: str
    version: str
    body: str
    origin: str
    path: Path
    claims: tuple[Claim, ...] = ()
    measured_with: str = ""

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "kind": self.kind,
            "version": self.version,
            "measured_with": self.measured_with,
            "origin": self.origin,
            "claims": [claim.public_dict() for claim in self.claims],
            "body": self.body,
        }


def _strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    raise ValidationError(f"Expected a string or list of strings, got {type(value).__name__}")


def _load_practice(path: Path, origin: str) -> Practice:
    header, body = parse_frontmatter(path.read_text(encoding="utf-8"), path)
    practice_id = str(header.get("id", "")).strip() or path.stem
    status = str(header.get("status", "convention"))
    if status not in PRACTICE_STATUSES:
        raise ValidationError(
            f"{path} has status {status!r}", allowed=sorted(PRACTICE_STATUSES)
        )
    enforced_by = _strings(header.get("enforced_by"))
    unknown = [code for code in enforced_by if code not in CHECK_CODES]
    if unknown:
        raise ValidationError(
            f"{path} claims to be enforced by unknown check(s) {', '.join(unknown)}",
            known=sorted(CHECK_CODES),
        )
    return Practice(
        id=practice_id,
        title=str(header.get("title", practice_id)),
        domain=str(header.get("domain", "general")),
        status=status,
        body=body,
        origin=origin,
        path=path,
        learned_on=str(header.get("learned_on", "")),
        enforced_by=enforced_by,
        evidence=_strings(header.get("evidence")),
        cost=str(header.get("cost", "")),
        supersedes=str(header.get("supersedes", "")),
    )


def _load_provider(path: Path, origin: str) -> ProviderProfile:
    header, body = parse_frontmatter(path.read_text(encoding="utf-8"), path)
    provider_id = str(header.get("id", "")).strip() or path.stem

    claims: list[Claim] = []
    seen: set[str] = set()
    for raw in header.get("claims", []) or []:
        if not isinstance(raw, dict):
            raise ValidationError(f"Each claim in {path} must be a table")
        claim_id = str(raw.get("id", "")).strip()
        if not claim_id:
            raise ValidationError(f"A claim in {path} is missing an id")
        if claim_id in seen:
            raise ValidationError(f"Duplicate claim id {claim_id!r} in {path}")
        seen.add(claim_id)
        status = str(raw.get("status", "unmeasured"))
        if status not in CLAIM_STATUSES:
            raise ValidationError(
                f"Claim {claim_id!r} in {path} has status {status!r}",
                allowed=sorted(CLAIM_STATUSES),
            )
        claims.append(
            Claim(
                id=claim_id,
                claim=str(raw.get("claim", "")),
                status=status,
                measured_on=str(raw.get("measured_on", "")),
                evidence=_strings(raw.get("evidence")),
                impact=str(raw.get("impact", "medium")),
                workaround=str(raw.get("workaround", "")),
            )
        )

    return ProviderProfile(
        id=provider_id,
        title=str(header.get("title", provider_id)),
        kind=str(header.get("kind", "unknown")),
        version=str(header.get("version", "")),
        body=body,
        origin=origin,
        path=path,
        claims=tuple(claims),
        measured_with=str(header.get("measured_with", "")),
    )


def load_practices(project_root: Path | None = None) -> list[Practice]:
    by_id: dict[str, Practice] = {}
    for origin, root in _roots(project_root):
        directory = root / "practices"
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            practice = _load_practice(path, origin)
            by_id[practice.id] = practice
    return sorted(by_id.values(), key=lambda item: (item.domain, item.id))


def load_providers(project_root: Path | None = None) -> list[ProviderProfile]:
    by_id: dict[str, ProviderProfile] = {}
    for origin, root in _roots(project_root):
        directory = root / "providers"
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            profile = _load_provider(path, origin)
            by_id[profile.id] = profile
    return sorted(by_id.values(), key=lambda item: item.id)


def practices_for_check(check_code: str, project_root: Path | None = None) -> list[Practice]:
    """The recorded reasoning behind one automated finding.

    A finding tells someone what is wrong. The practice tells them why it
    matters and what it cost the last time nobody noticed.
    """

    return [
        practice
        for practice in load_practices(project_root)
        if check_code in practice.enforced_by and practice.status != "refuted"
    ]


@dataclass(frozen=True, slots=True)
class Coverage:
    """How much of what the production knows the software actually enforces."""

    practices: int = 0
    enforced: int = 0
    unenforced: tuple[str, ...] = ()
    checks_without_practice: tuple[str, ...] = ()
    claims: int = 0
    measured_claims: int = 0
    by_domain: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def percentage(self) -> int:
        return round(self.enforced / self.practices * 100) if self.practices else 0

    def public_dict(self) -> dict[str, Any]:
        return {
            "practices": self.practices,
            "enforced": self.enforced,
            "percentage": self.percentage,
            "unenforced": list(self.unenforced),
            "checks_without_practice": list(self.checks_without_practice),
            "claims": self.claims,
            "measured_claims": self.measured_claims,
            "by_domain": {
                domain: {"practices": total, "enforced": enforced}
                for domain, (total, enforced) in sorted(self.by_domain.items())
            },
        }


def coverage(project_root: Path | None = None) -> Coverage:
    practices = load_practices(project_root)
    providers = load_providers(project_root)

    enforced = [practice for practice in practices if practice.enforced]
    claimed_codes = {code for practice in practices for code in practice.enforced_by}

    by_domain: dict[str, tuple[int, int]] = {}
    for practice in practices:
        total, done = by_domain.get(practice.domain, (0, 0))
        by_domain[practice.domain] = (total + 1, done + (1 if practice.enforced else 0))

    all_claims = [claim for profile in providers for claim in profile.claims]
    return Coverage(
        practices=len(practices),
        enforced=len(enforced),
        unenforced=tuple(
            practice.id for practice in practices if not practice.enforced
        ),
        checks_without_practice=tuple(sorted(CHECK_CODES - claimed_codes)),
        claims=len(all_claims),
        measured_claims=len([claim for claim in all_claims if claim.status == "measured"]),
        by_domain=by_domain,
    )
