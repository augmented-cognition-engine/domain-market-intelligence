# ACE Market Intelligence

**Governed market sensemaking on the shared ACE foundation.**

ACE Market Intelligence is an independently versioned ACE domain product. Its installable package
is an inert, JSON-only Domain Pack for turning attributable market observations into
domain-governed Shifts, Signals, Cases, and Briefs through the shared ACE Core + Intelligence
runtime.

It supplies Market vocabulary, source mappings, material-change policy, personas, synthesis and
feedback policy, connector fixtures, and product evidence. It does not implement a second reasoning
engine, graph, state store, authority system, detector runtime, or feedback loop.

[Install](#install) · [Architecture](#what-you-install-and-what-you-get) ·
[Proof](#current-proof-surface) · [Roadmap](ROADMAP.md) · [Security](SECURITY.md) ·
[Contributing](CONTRIBUTING.md)

- **Distribution:** `ace-domain-market-intelligence` 0.7.0
- **Requires:** Python 3.12 and `ace-core>=0.8.2,<0.9`
- **Artifact boundary:** JSON-only, data-only, inert
- **Release:** public
  [`v0.7.0`](https://github.com/augmented-cognition-engine/domain-market-intelligence/releases/tag/v0.7.0)
  and [`0.7.0 on PyPI`](https://pypi.org/project/ace-domain-market-intelligence/0.7.0/).
  GI2 and the historical external GC1 consumer journey remain frozen in their original evidence.

The 0.7 release projects Market’s analyst intelligence loop through the
single governed resource plane with an explicit `no_action` Decision and non-live Feedback. That
proof is additive and does not change the public 0.6.0 installation contract; see the
[candidate evidence](docs/evidence/intelligence-os-v0.8-core-candidate-v1.md).

## What you install, and what you get

The product is split into three layers, and this repository owns only the third.

| Layer | Distribution | What it is |
|---|---|---|
| **ACE Core** | `ace-core` (0.8.2 published) | The runtime: identity, graph, immutable records, temporal validation, lineage, reasoning, authority, decisions, outcomes, receipts, and replay. |
| **ACE Intelligence** | shipped with ACE Core | The domain-neutral contracts: pack compilation, activation, Observation, Entity Snapshot, detection, routing, Case, Brief synthesis, epistemic status, and feedback. |
| **Market Intelligence Domain Pack** | `ace-domain-market-intelligence` (this repository) | JSON declarations only — ontology, source mappings, detection, personas, synthesis, feedback policy, and frozen conformance fixtures. |

Installing the Domain Pack adds **data**, not behavior. The wheel contains no Python modules, entry
points, install hooks, connector, or application UI. ACE Core compiles those JSON modules and does
the reasoning. Live sensing requires a separately reviewed connector; see
[Connector boundary](#connector-boundary).

### Install

Install the public 0.7.0 package with either command:

```bash
uv add "ace-domain-market-intelligence==0.7.0"
```

```bash
pip install "ace-domain-market-intelligence==0.7.0"
```

The 0.7.0 release gate used the real public `ace-core==0.8.2` and World Intelligence 0.12.0
artifacts in a checkout-free environment. The published 0.6.0 artifact and its Core 0.4
compatibility metadata remain unchanged.

Resolve the pack data from the installed distribution:

```python
import json
from importlib.resources import files

manifest = json.loads(
    files("domain_packs.market_intelligence").joinpath("manifest.json").read_text(encoding="utf-8")
)
print(manifest["metadata"]["pack_id"])  # market_intelligence
```

## Product loop

```text
authorized evidence → Observation → Entity Snapshot
                           ├────────→ Signal ──┐
                           └────────→ Shift ───┼→ Case / Brief → Decision → Outcome
                                               └→ governed feedback proposal
```

This is a typed DAG, not a forced pipeline. A Shift need not become a Signal, a Signal need not
become a Brief, and no downstream resource grants itself authority.

## Domain scope

The full Market Intelligence domain is intended to cover:

- competitive intelligence;
- product and pricing intelligence;
- market and megatrend understanding;
- customer and voice-of-customer understanding;
- narrative, claim, and messaging drift;
- campaign and go-to-market signals; and
- competitive, event, weekly-summary, GTM, and de-positioning Brief policies.

These are Market-domain types and taxonomies. The shared machinery remains in ACE.

The current frozen proof is deliberately narrower: its compiled 0.3.0 pack models competitor and
product entities, public price observations, numeric price Shifts, competitive Signals, persona
routing, and a governed competitive-price Brief. Additive 0.4.0 and 0.5.0 pack revisions add ordered
synthesis and bounded decision/outcome policy; the frozen 0.6.0 conformance packet adds the P1F
LIVE bridge. The 0.7.0 candidate adds catalog onboarding metadata without pretending that every
planned Market facet is implemented.

## Current proof surface

The repository carries the frozen Market P1 packets:

- P1A/P1B: deterministic price observations, numeric Shift, Signal routing, and Brief resources;
- P1C1/P1C2: declarative source mapping and governed LIVE source admission;
- P1D1: governed Case-bound Brief synthesis and exact replay;
- P1E: Decision, Outcome, and bounded feedback proposal with no silent policy change; and
- P1F: the paired LIVE Shift → Signal → route → Brief bridge through unchanged ACE.

## Connector boundary

The separately packaged public-product connector accepts only an injected reviewed transport. It is
executable host software, not Domain Pack content. It is source-available here for conformance but
is not a dependency of the Domain Pack and is not published by the root release. Installing
`ace-domain-market-intelligence` never installs, discovers, registers, or authorizes it.

## GI2: cross-domain falsification

The public release proved a clean installation of ACE plus both independently packaged domains:

```text
ace-core 0.4.1
  + ace-domain-market-intelligence 0.6.0
  + ace-domain-world-intelligence 0.8.0
```

Both packs compiled and activated through unchanged ACE, retained distinct pack, entity, persona,
policy, and authority identities, and survived independent deactivation. A co-install alone was not
enough. This supplied the second public-domain evidence that closed Core roadmap outcome GI2.

Publication identities and verification are recorded in the
[0.6.0 release record](docs/releases/market-intelligence-v0.6.0.md). This is an exact historical
receipt; World has since released 0.9.0 against Core 0.5.0.

## GC1: external governed-cognition consumer

Market Intelligence is the first external consumer of ACE's public governed-cognition builder
interface. Its two-phase verifier teaches a reusable market reasoning pattern from an accepted
task, inspects and approves the proposal, proves exact material use, crosses a real ACE restart,
proves exact later use, retires the revision, and requires subsequent selection to fail closed.

The verifier imports no Core internals and remains outside the inert wheel. See the
[external GC1 journey](docs/gc1-external-consumer.md) and the
[public 0.4.4 execution record](docs/evidence/gc1-market-external-consumer-v1.md). The journey passed
from a clean public-index installation, crossed a real API restart over durable state, and rejected
a distinct required use after retirement. ACE Core owns the final GC1 roadmap reconciliation.

## Verification

Use Python 3.12 and the locked environment:

```bash
uv sync --frozen --no-install-project
uv run --no-sync pytest
uv run --no-sync pytest tests/test_release_contract.py
uv run --no-sync ruff check --no-cache tests scripts/gc1_external_consumer.py
uv run --no-sync ruff format --check --no-cache tests scripts/gc1_external_consumer.py
```

The immutable historical artifact hashes, clean-install evidence, cross-domain GI2 proof, and
limitations are recorded in the [0.6.0 release record](docs/releases/market-intelligence-v0.6.0.md).
The 0.7 candidate packet is in
[docs/releases/market-intelligence-v0.7.0-candidate.md](docs/releases/market-intelligence-v0.7.0-candidate.md).
The GC1
consumer evidence is a later additive proof over the unchanged inert 0.6.0 artifact.

## Guardrails

- A pack contains no imperative control flow or credentials.
- Source repetition is not independent corroboration.
- Claims retain attribution and corrections append rather than rewrite history.
- Installing a pack does not compile, activate, authorize, execute, deliver, or publish anything.
- Models may propose; deterministic policy and explicit human authority govern activation and
  consequential use.
- Content creation, campaign activation, publishing, and project management are downstream
  consumers, not part of this package.

## Roadmap and project status

The [Market Intelligence roadmap](ROADMAP.md) owns current domain direction, and release history is
in [`CHANGELOG.md`](CHANGELOG.md). Core, World, and Market version independently; each compatibility
window advances only with its own conformance and public-artifact evidence.

## Community and security

- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Issues](https://github.com/augmented-cognition-engine/domain-market-intelligence/issues)

## License

Apache-2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE). Existing work is copyright Edwin
Amirian; contributors retain copyright in their contributions and license them under Apache-2.0.
