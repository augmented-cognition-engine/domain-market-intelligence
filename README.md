# ACE Market Intelligence

ACE Market Intelligence is an inert Domain Pack for turning attributable market observations into
domain-governed Signals, Shifts, Cases, and Briefs through the shared ACE Core + Intelligence
runtime.

It supplies marketing meaning and policy. It does not implement a second reasoning engine, graph,
state store, authority system, detector runtime, or feedback loop.

- **Distribution:** `ace-domain-market-intelligence` 0.6.0 release candidate
- **Requires:** Python 3.12 and `ace-core>=0.4.1,<0.5`
- **Artifact boundary:** JSON-only, data-only, inert
- **Status:** initial public repository; tag, GitHub Release, and PyPI publication are pending

## Architecture

| Layer | Owner |
|---|---|
| ACE Core | Identity, time, immutable state, graph mechanics, reasoning, authority, decisions, outcomes, receipts, and replay. |
| ACE Intelligence | Domain-neutral Observation, Entity state, Signal, Shift, Case, Brief, pack compilation, activation, routing, synthesis, and feedback contracts. |
| Market Intelligence Domain Pack | Competitor, product, claim, campaign, market, customer-segment, event, materiality, persona, mapping, detector, synthesis, and outcome declarations. |
| Connectors | Separately reviewed source translation. They are executable, optional, and never bundled into this wheel. |

The user-facing grammar is a DAG, not a forced pipeline:

```text
evidence → Observation → entity state
              ├────────→ Signal ──┐
              └────────→ Shift ───┼→ Case / Brief → Decision → Outcome
                                  └→ governed feedback proposal
```

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
synthesis and bounded decision/outcome policy; the 0.6.0 distribution adds the P1F LIVE-bridge
conformance packet without pretending that every planned Market facet is implemented.

## Install

The package will install with either command after the 0.6.0 public release:

```bash
uv add "ace-domain-market-intelligence==0.6.0"
```

```bash
pip install "ace-domain-market-intelligence==0.6.0"
```

Installing the Domain Pack adds data, not behavior. The wheel contains no Python modules, entry
points, install hooks, connector, or application UI.

## Current proof surface

The repository carries the frozen Market P1 packets:

- P1A/P1B: deterministic price observations, numeric Shift, Signal routing, and Brief resources;
- P1C1/P1C2: declarative source mapping and governed LIVE source admission;
- P1D1: governed Case-bound Brief synthesis and exact replay;
- P1E: Decision, Outcome, and bounded feedback proposal with no silent policy change; and
- P1F: the paired LIVE Shift → Signal → route → Brief bridge through unchanged ACE.

The separately packaged public-product connector accepts only an injected reviewed transport. It is
source-available here for conformance but is not a dependency of the Domain Pack and is not planned
for publication in the 0.6.0 root release.

## GI2: cross-domain falsification

The release candidate must prove a clean installation of ACE plus both independently packaged
domains:

```text
ace-core 0.4.1
  + ace-domain-market-intelligence 0.6.0
  + ace-domain-world-intelligence 0.8.0
```

Both packs must compile and activate through unchanged ACE, retain distinct pack, entity, persona,
policy, and authority identities, and survive independent deactivation. A co-install alone is not
enough. Passing this gate supplies the second public-domain evidence needed to close Core roadmap
outcome GI2.

Current verification and remaining publication steps are recorded in the
[0.6.0 release-candidate record](docs/releases/market-intelligence-v0.6.0.md).

## Guardrails

- A pack contains no imperative control flow or credentials.
- Source repetition is not independent corroboration.
- Claims retain attribution and corrections append rather than rewrite history.
- Installing a pack does not compile, activate, authorize, execute, deliver, or publish anything.
- Models may propose; deterministic policy and explicit human authority govern activation and
  consequential use.
- Content creation, campaign activation, publishing, and project management are downstream
  consumers, not part of this package.

## License

Apache-2.0.
