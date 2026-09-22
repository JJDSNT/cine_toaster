# ADR 0011: Reuse from copyleft sources is by reimplementation, not incorporation

Status: accepted

## Context

OpenMontage was evaluated as a source of mechanisms Cine Toaster wants: style
playbooks as data, a prompt builder that derives its text from structured shot
language, a mechanical score that predicts whether a plan will render as a
slideshow, and a provider registry that carries cost and fallback across fifty
generation providers. The mechanisms are good and the evaluation was worth
doing.

It is licensed under the GNU Affero General Public License v3, with no
exception and no dual licence. Cine Toaster serves a web interface, so the
network clause applies to it rather than being theoretical: software derived
from an AGPL work and offered over a network must offer its complete source
under the same terms to everyone who uses that interface.

Cine Toaster has no LICENSE file. Its licensing is an open question, and the
first route considered for reuse — a git submodule — would have answered that
question as a side effect of a convenience. A dependency must not decide what
the project is.

The size of the exchange also matters. The immediate target was `styles/`: five
YAML playbooks of roughly three kilobytes each. Reaching them through a
submodule would attach sixty thousand lines of Python, a hundred and sixty-seven
tools, and a renderer's dependency tree. That is the shape of mistake ADR 0010
names — scaffolding mistaken for architecture — and the shape CT-0012 already
refused when it moved a provider data plane and left the control plane behind.

## Decision

No copyleft-licensed source enters this repository. Not vendored, not as a
submodule, not as file-level copies. This covers data files as fully as code: a
YAML playbook is an authored work, and copying it is incorporation.

Mechanisms learned from such a source are reimplemented from their description.
A five-part prompt structure, six scored dimensions with a failure threshold, the
idea that consistency anchors belong to a style rather than to a scene — these
are structures and measurements, not the licensed artifact. The files are.

When a reimplementation is traceable to an external source, the work record
names the source, its licence, and what was taken. Provenance stays auditable
and the line stays visible to whoever reads the code next.

Permissively licensed dependencies — MIT, BSD, Apache-2.0 — are ordinary
dependencies and are unaffected by this decision.

## Consequences

Reuse costs implementation time instead of integration time. That is the trade
being bought, and it is worth buying: every mechanism worth taking is small,
while the repository it lives in is not.

Cine Toaster's own licence remains a deliberate choice, made when there is a
reason to make it, rather than inherited from the first useful dependency.

An evaluation that ends in "we will not take the code" is still a successful
evaluation. The reading produced a list of mechanisms and a list of things not
to copy; both are recorded in CT-0014.
