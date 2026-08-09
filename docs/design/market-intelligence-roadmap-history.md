# ACE Market Intelligence solution roadmap

**Status:** Architecture locked; M0/P0 and every Market consumer packet through P1F complete; Platform P1 complete; Platform P2 World Intelligence falsification substantially complete as of 2026-08-07, with acceptance-gate items 1 and 6 still open
**Date:** 2026-08-05 (status reconciled 2026-08-07)
**Current repository:** `ace-ext-b2b-marketing`
**Target Domain Pack:** `ace-domain-market-intelligence`
**Target Solution Bundle:** `ace-solution-market-intelligence`
**Platform dependency:** one ACE distribution containing the Core and Intelligence bounded
contexts described by the
[ACE manifesto](https://github.com/augmented-cognition-engine/core/blob/main/MANIFESTO.md) and the
IP1–IP5 sequence in the
[ACE public roadmap](https://github.com/augmented-cognition-engine/core/blob/main/ROADMAP.md)

The legacy filename is retained while the repository migrates from one executable marketing
extension into a composed Market Intelligence solution.

## Product decision

ACE Market Intelligence is the first production Domain Pack, public reference application, and
Solution Bundle for ACE Intelligence. It proves that a real vertical can supply ontology,
analytical policy, source mappings, detectors, personas, Brief templates, action declarations, and
evaluations without owning or forking the ACE runtime.

Core and Intelligence come together as ACE. They remain separate internal bounded contexts so
their responsibilities and dependencies are testable:

- **Core** governs evidence, temporal state, graph mechanics, reasoning, identity, authority,
  execution, decisions, outcomes, learning, and receipts.
- **Intelligence** governs the universal intelligence-resource grammar, orientation, detection,
  synthesis, operations, and Ontology Toolchain.
- **The Market Domain Pack** supplies inert marketing-intelligence meaning and policy.
- **Organization Overlays** supply deployment-specific subjects, aliases, thresholds, personas,
  source declarations, and private policy within pack-declared bounds.
- **Adapters and strategy plugins** supply separately reviewed executable integrations or
  specialized algorithms.
- **The reference application** supplies the analyst experience.
- **The Solution Bundle** links exact dependencies; it owns no canonical state and grants no
  authority.

Content creation, production, translation, publishing, campaign activation, and project management
remain downstream consumers. They may consume approved intelligence through stable APIs, events,
or explicitly authorized delivery adapters; they do not define this product boundary.

## Universal product grammar, Market flavor

Signal, Shift, and Brief are universal user-facing resource lanes, not a mandatory pipeline:

| Resource | Question answered | Market Intelligence examples |
|---|---|---|
| **Observation** | What did an attributable source report or measurement record? | published price, product-page text, campaign copy, survey response |
| **Signal** | What may deserve attention? | new competitor claim, unusual price observation, emerging buyer concern |
| **Shift** | What has materially changed against an explicit baseline? | price move, messaging pivot, category acceleration, customer-needs movement |
| **Brief** | What does the frozen evidence mean and which decision should be considered? | newsflash, weekly summary, event analysis, GTM brief, de-positioning recommendation |

Competitive, product, market, customer, performance, and narrative intelligence are Market-domain
facets. CAP, GTM, pricing, hiring, claims, launches, and megatrends are topics or pack-declared
taxonomies. None becomes another ACE architecture or mutually exclusive platform product kind.

The derivation shape is:

```text
evidence → observation → market entity state
              │                    ├──→ shift ──┐
              └──→ signal ─────────┴────────────┼──→ case / brief
                                                ↓
                                    decision → action → outcome
                                                         ↓
                                            governed feedback proposal
```

A Signal need not establish a Shift. A deterministic delta may establish a Shift before attention
routing creates a Signal. A scheduled or question-driven Brief may use frozen entity state and
Observations without a new Signal or Shift. Acceptance fixtures may deliberately exercise all
resources without turning them into automatic promotion stages.

## Packaging model

| Artifact | Market Intelligence contents | Executable? |
|---|---|---:|
| **Domain Pack** | Entity, relation, event, Signal, Shift, action, outcome, source-mapping, persona, policy, prompt, template, and evaluation declarations | No |
| **Organization Overlay** | Watched organizations and products, local aliases, thresholds, personas, source definitions, private taxonomies, policy, and secret-binding references | No |
| **Domain Activation** | Exact Pack IR and Overlay IR plus adapter/plugin, persona, authority, compiler, compatibility, and conformance bindings | No embedded code |
| **Source/delivery adapter** | Authorization, retrieval, normalization, delivery, writeback, credentials, retries, and external failure handling | Yes, separately reviewed |
| **Strategy plugin** | A specialized resolver or detector that cannot be expressed safely through built-in strategies | Yes, separately reviewed |
| **Reference application** | Briefing, investigation, review, source administration, subscription, and delivery experience | Yes, replaceable client |
| **Solution Bundle** | Hash-pinned dependency manifest for the pack, overlay templates, adapters/plugins, app, SDKs, docs, and fixtures | References code; grants no capability |

The lifecycle invariants are:

```text
install bundle ≠ compile pack ≠ activate domain ≠ authorize adapter ≠ execute action
```

A pack contains no imperative control flow, Python or native code, network or filesystem access,
secret access, executable templates, mutable remote resources, or auto-loaded entry points.
Credentials live only in runtime secret storage; Overlays contain opaque secret references.

## Ownership map

| Concern | Canonical owner | Market contribution |
|---|---|---|
| Evidence and temporal state | Core | Pack declares source meaning and mappings; bound adapters capture exact source material. |
| Entity graph mechanics | Core | Intelligence resolves and projects; pack declares competitor, product, claim, campaign, executive, market, segment, and event meaning. |
| Intelligence resources | Intelligence | Pack declares Market types, analytical policy, materiality, exemplars, personas, and templates. |
| Ontology Toolchain | Intelligence over Core governance | Market supplies compiler and conformance fixtures, never a private loader. |
| Reasoning | Core | Intelligence assembles Briefs; pack supplies approved Market frameworks, prompts, exemplars, and limitations. |
| Decisions and outcomes | Core | Pack declares eligible dispositions, action and outcome types, and evaluation measures. |
| External effects | Core authority and execution receipt + bound adapter | Pack declares the verb and requirements; an adapter performs the approved effect. |
| Product experience | Reference application | Market Briefing, investigation, reviews, monitors, subscriptions, sources, and delivery. |
| Distribution | Solution Bundle | Links exact dependencies and public fixtures; never becomes a state or authority plane. |

No milestone is complete if this repository creates a second reasoning plane, graph engine, memory
store, provider router, provenance model, authorization system, decision/outcome lifecycle,
activation loader, or generic Intelligence runtime.

## Modular pack direction

The pack language must not freeze every future source, detector, and Brief DSL into one giant root
manifest. A small stable manifest references independently versioned, content-addressed modules:

```yaml
contract: ace.intelligence.domain-pack-manifest/v1alpha1
metadata:
  pack_id: market_intelligence
  version: 0.1.0
compatibility:
  intelligence: ">=0.4,<0.5"
  compiler: ace.intelligence.pack-compiler/v1alpha1
modules:
  - module_id: market_ontology
    contract: ace.intelligence.ontology/v1alpha1
    path: modules/ontology.json
    digest: sha256:<exact-lowercase-digest>
capability_requirements:
  - capability: ace.source.snapshot/v1
overlay_slots:
  - slot: watched_subjects
  - slot: organization_aliases
```

P0 began with the typed `ontology/v1alpha1` module. P1 now adds independently versioned
source-mapping, numeric-detection, persona-routing, structural-synthesis, and bounded
decision-outcomes modules while leaving semantic strategy, executable action, and broad evaluation
modules for later evolution. The root envelope remains stable. Intelligence owns the closed
validator table; a pack cannot register its own compiler or validator.

The Market ontology begins with:

- entities: competitor, product, claim, campaign, executive, market, customer segment, market event;
- relations: makes, claims, targets, prices-at, employs, competes-with, responds-to;
- later detector configuration: price move, claim drift, narrative shift, launch change, customer
  concern movement;
- personas: competitive-intelligence analyst, product marketer, communications strategist;
- Brief templates: newsflash, weekly summary, event analysis, GTM strategy brief, de-positioning
  alert; and
- action declarations: investigate, validate Shift, approve or reject Brief, notify subscriber,
  and record outcome.

These are pack declarations, not lower-layer branches or implementations.

## Program sequence

The sequence is deliberately vertical and paired. Core and Intelligence add one universal
capability while Market consumes it in the same acceptance packet; neither half completes alone.
After the narrow LIVE bridge, ACE challenges the abstraction with World Intelligence before
broadly expanding either domain or freezing generated SDKs. Corporate Strategy follows as the
third-domain proof.

### M0 — Preserve truth and establish the pivot — complete

The existing 55-route surface was classified; cross-language source contracts were reconciled;
initial source and Signal records were added; focused Python, Core-integration, Canvas, and
TypeScript checks passed. M0 preserves migration truth. It does not validate the legacy mixed
`Signal.signal_type` taxonomy or the executable extension as the future pack loader.

### Platform P0 — Lock the boundary and compiler substrate — complete in working tree

**Outcome:** inert packs and immutable activation intent have stable additive contracts before any
new intelligence runtime is built.

Core-repository work:

1. Establish additive `ace.intelligence` and narrow `ace.core` public contract facades without
   moving the legacy engine.
2. Define the root Domain Pack manifest, modular `ontology/v1alpha1`, compiler diagnostics, immutable
   Pack IR, Organization Overlay, Domain Activation specification, and append-only Activation
   revision contracts.
3. Implement a pure compiler: `manifest + resource bytes → deterministic Pack IR`.
4. Make the existing executable `ace.extensions` loader explicitly ineligible for Domain Packs.
5. Add package, import, no-execution, path, digest, determinism, compatibility, and boundary tests.

Acceptance gate:

- minimal Market and Threat ontology fixtures compile through the identical function;
- equivalent ordering produces byte-identical IR and digest, while material change changes it;
- unknown contracts, fields, capabilities, paths, digests, references, and cycles fail closed with
  path-specific diagnostics;
- compilation performs no discovery, import, database mutation, network request, model call,
  credential lookup, clock read, environment default, or registry mutation;
- Activation specifications pin exact artifacts and reject missing capability or authority
  bindings;
- rollback is represented as a new append-only Activation revision, never record mutation; and
- no route, MCP tool, database schema, runtime entity, Signal, Shift, or Brief is added in P0.

Current P0 slice: the additive Core working tree now contains lightweight `ace.core.contracts`,
strict modular `ace.intelligence` pack/ontology contracts, a pure JSON compiler, Pack IR, bounded
Organization Overlays, exact Activation specifications, append-only transition preparation,
cross-domain Market/Threat fixtures, import guards, and wheel packaging coverage. It remains an
unreleased alpha substrate: catalog persistence, Core approval lookup, current-head compare-and-
swap, runtime registration, migrations, generated SDKs, and intelligence resources are not built.

### Platform P1 — Intelligence alpha and one thin Market slice — active

**Outcome:** the smallest complete Market decision loop runs through common Core and Intelligence
contracts.

Frozen acceptance fixture (prepared data now; captured public evidence is required for P1 completion):

```text
two prepared same-currency product-price snapshots
→ exact source Observations and entity-snapshot lineage with upstream cutoff and availability
→ explicit price baseline
→ material PriceMove Shift
→ persona-routed Signal
→ evidence-cited Brief
→ named Decision or explicit no-action
→ later Outcome
```

The fixture exercises all three lanes but preserves DAG semantics. Scope includes exact/alias
resolution, one deterministic detector, synchronous Brief assembly through Core reasoning,
activation preview/approval/rollback, Core-managed persistence, as-of replay, and restart. Live web
capture, scheduling, semantic-detector breadth, generated SDKs, external action execution, route
migration, and workbench redesign remain out.

Acceptance gate:

- every record pins its evidence, policy, compiler, pack, Overlay, and Activation revisions;
- as-of replay cannot see later observations;
- every Brief claim is cited or explicitly marked inference;
- unauthorized and cross-product reads fail closed;
- prepared fixtures never enter live counts, routing, delivery, or learning;
- restart preserves exact identities and receipts; and
- the Market solution adds no parallel graph, reasoning, authorization, decision, or outcome engine.

Current P1 slice:

- Core and Intelligence now expose strict immutable Observation, Entity Snapshot, Signal, Shift,
  Citation, grounded-claim, and Brief contracts with exact activation, as-of, lineage,
  prepared/live, evidence-acquisition identity, and host-resolvable acquisition-receipt references;
  every lineage edge carries the upstream resource's as-of cutoff and availability time;
- the shared pack compiler now validates ontology, declarative source-mapping, numeric-detection,
  persona-routing, and structural-synthesis modules without importing domain code;
- a prepared-only runtime binding derives the activation reference from one locally prepared
  desired-active revision, verifies its exact compiled Pack IR, and resolves detector and persona
  policy only from that pack; numeric interpretation validates each Snapshot against the bound
  ontology's required/type/cardinality declarations and fails closed outside the exact supported
  integer range; the binding cannot grant live authority;
- the Market pack v0.3 declares `competitor`, `product`, `makes`, the closed
  `product_price_snapshot` source mapping, the `product_price_move` detector,
  same-currency comparison context, the competitive-intelligence analyst route, and a competitive
  price-move Brief structure; it also requests the exact public source-snapshot capability and
  source-read authority that a host must bind, without embedding an adapter or granting authority;
- a Market-owned prepared public-product-page boundary now fixes source meaning, explicit
  PREPARED-only capability-binding identity, immutable Core-derived source identity,
  acquisition-receipt reference/digest provenance, nullable publication time, distinct observed and
  available time, and same-source/same-product/same-currency comparison policy; normalization now
  lives only in the compiler-supported mapping module and evidence identity is not copied into the
  `product` attributes;
- the mapping deliberately uses the mode-neutral
  `source_definition:public-northstar-edge-x1`: source identity describes the source, while
  PREPARED versus LIVE belongs to acquisition and admission mode, allowing P1C2 to reuse the exact
  mapping without an identity fork;
- the prepared golden fixture constructs Core canonical snapshots and resolved product subjects,
  then uses the public P1C1 interpreter to produce the two Observations and product-only
  exact-lineage Entity Snapshots; competitor and relationship context remains separate. The result
  produces a 10% price-decrease Shift, optionally routes the
  Signal, and preserves the historical manually authored structurally cited Brief through shared
  Intelligence contracts; eight
  negative vectors fail closed for exact source definition, HTTPS, payload-digest and receipt-reference integrity,
  cross-product and cross-currency comparison, unavailable evidence, and prepared/live leakage;
  the historical pack's Brief template remains declared and compiler-validated; and
- the installable extension distribution now includes the inert Market pack plus a digest-pinned
  prepared conformance inventory for the boundary, positive scenario, negative scenarios, and exact
  durable batch, transaction, resource, activation-commit, and attention-receipt identities; and
- Market now consumes Platform P1B through only public `ace.application`, `ace.core`,
  `ace.intelligence`, and `ace.testing` seams: it Core-commits and reloads the exact activation,
  atomically admits the seven-resource PREPARED derivation plus one route receipt, replays it
  idempotently and through a fresh service, proves historical isolation, and leaves no rejected-case
  residue. Every admitted value remains PREPARED, committed-but-non-live, and without delivery
  authority.

This is not the Platform P1 acceptance gate. Market P1C1 passes the public compiler and PREPARED
source-mapping interpreter as well as the public durable PREPARED conformance seam, including an
exact route-or-suppression receipt for the fixture's declared route.
Platform separately owns and proves the production SurrealDB adapter; Market neither reimplements
that adapter nor makes an independent production-durability claim. Market P1C2 now proves live
adapter binding, use-time capability and authority resolution, deterministic injected capture,
Core acquisition provenance, atomic LIVE admission, and exact same/fresh-service replay against the
reviewed Platform P1C2 wheel. The inert Pack and root extension wheel exclude adapter code; the
repository contains its separately packaged frozen v0.1.1 adapter source and wheel evidence. The
superseded v0.1.0 wheel remains audit evidence only. Actual
public-evidence capture remains gated on an authorized stable endpoint and reviewed transport.
Market P1D1 adds an immutable inert 0.4.0 release whose synthesis module alone opts into ordered
`v1alpha2`. Activation revision 2 admits a fresh PREPARED six-resource closure and route receipt
with no prebuilt Brief; public governed Core reasoning and Intelligence assembly resolve and enforce
the exact template/persona, then atomically append the canonical Brief and synthesis receipt.
Revision 3 is an append-only rollback to the exact 0.3.0 revision-1 specification. A fresh service
with both immutable Packs replays the revision-2 request provider-free, and the historical manual
P1B Brief remains readable. Market P1E adds the inert 0.5.0 release: every 0.4.0 module remains
byte-identical and one `decision-outcomes/v1alpha1` module declares the eligible persona, route,
Decision/no-action, Outcome measure, bounds, and categorical adjustment. Activation revision 4
reviews the exact P1D1 Brief, records a Core-owned Decision and later Outcome, produces an
Intelligence proposal, then requires separate Core approval to commit PREPARED policy state. Exact
replay, stale-proposal rejection, and fresh-service value `0.55` pass. Delivery, external action,
LIVE feedback, and operational learning remain open.
The existing
temporal belief projection cannot be adopted for this slice until its historical applicability
semantics are corrected.
The current Platform P1C2 host resolves use-time authority and mints the acquisition/admission
receipts for the narrow LIVE Observation and Entity Snapshot path. P1D1 is intentionally PREPARED
and route-triggered; LIVE Shift/Signal/routing remains a separate future bridge required before any
LIVE Brief claim.
The public-source boundary now points to the compiler-supported inert mapping module; the Market
tests use only public Core and Intelligence contracts and do not duplicate interpreter behavior.
P1C2 now adds a narrow, separately versioned adapter behind Platform's public live-ingress seam;
it never enters the Pack or root extension wheel. Legacy
`ace_ext_b2b_marketing/marketing/source_ingestion.py` remains broader compatibility code and is not
promoted or reused. The extension cannot declare its final `ace-core` runtime version until this P1
API is released. P1C2 and P1D1 retain their historical reviewed wheel evidence. Current P1E
cross-repo conformance uses exact Core 0.3.0 wheel SHA-256
`44287fe0f7cff79186c732d00d6b9eba5f44c508522aa2911f1a63a88a7fa68f` and Market wheel SHA-256
`041ca87ad62060d758615b2c7f00019fcd2bca90657096b7fe04ca8efce4eba4`; the installed probe resolves
Core imports and 0.5.0 pack resources from those artifacts and never silently falls back to an
older published Core.

### Platform P1F — Paired LIVE intelligence bridge — verified 2026-08-06

**Outcome:** Core and Intelligence supply the domain-neutral LIVE Shift → Signal → routing → Brief
path, and Market consumes that exact public path with one bounded competitive-change scenario.

Platform work belongs in `ace-core`: exact LIVE derivation requests, current activation and
authority checks, immutable admission, atomic receipts, replay, and fresh-service recovery. Market
work belongs here: one pack-declared detector, route, persona, template, public-source adapter
binding, and expected/negative conformance packet. Market must not add a private runtime, graph,
store, reasoning path, or authority system. The gate passes only when both repositories pass from
installed artifacts.

The paired gate now passes. Two governed LIVE public-product admissions at USD 1,200 and USD 1,080
flow through the public platform bridge into a material Shift, routed Signal, durable attention
receipt, and governed canonical LIVE Brief. Fresh-service derivation and Brief replay are exact;
the provider runs once for first synthesis and zero times during replay. Four negative cases reject divergent derivation replay, divergent Brief
replay, PREPARED promotion, and an unadmitted source coordinate.

The Market side adds only an inert 0.6.0 conformance packet and consumer harness. Core owns the
LIVE services, authority checks, reasoning, storage, receipts, and replay. Delivery authority is
false and there are no external actions or LIVE feedback effects.

### Platform P2 — World Intelligence falsification

**Outcome:** a source-diverse, rapidly changing, primarily semantic domain challenges the
abstraction while `v1alpha1` can still change and provides an understandable public showcase.

**Progress (2026-08-07):** World P2A, P2B, and P2C are all verified in the separate
`augmented-cognition-engine/domain-world-intelligence` project. The JSON-only pack compiles through unchanged ACE, passes
seven conformance tests and five negative mutations, and co-installs with Market. P2B closed every
World consumer contract request — `WI-CR-001` through `WI-CR-005` — via domain-neutral platform
capabilities: per-statement epistemic status, derivation-family independence, and supersession
impact. `ClaimGroundingKind` still expresses only `{cited, inference}`; no World vocabulary entered
either bounded context, and the leak test remains green. A deterministic public demonstration is
released as `0.7.0-rc1`, and P2C adds governed LIVE official-source admission as `0.8.0` over a
network-free transport.

**Still open in P2:** acceptance-gate item 1 (committed activation lifecycle, upgrade, and rollback
through unchanged ACE) and item 6 (Market and World **runtime** co-activation isolation — proven
today only at the install and compile level). A reviewed opt-in network transport and P2D LIVE
multi-source conflict/correction also remain. See the
[World Intelligence roadmap](ace-world-intelligence-domain-roadmap-2026-08-06.md).

Use a minimal World Intelligence pack:

```text
official records + attributable statements + independent reporting
→ actor + institution + issue + event + policy + claim state
→ event-status, claim-support, correction, or narrative Shift
→ public-attention Signal
→ cited reality / what-changed Brief
→ Decision / no-action / Outcome
```

It needs no production feed or broad connector suite. It must pressure event and claim identity,
source-family independence, corrections, contradictions, semantic change, uncertainty, and
perspective-aware synthesis without creating a second runtime or a hidden truth score. Market and
World must run simultaneously through the same compiler, activation model, resource contracts,
and conformance runner without catalog, entity, persona, authority, or policy leakage.
Deactivating one must not impair the other. No actor, institution, jurisdiction, issue, event,
claim, policy, narrative, publisher, or politics-specific branch may enter Core or Intelligence.

Freeze `v1beta1` only after P2. The first domain proves value; the second tests the abstraction.

### Platform P3 — Corporate Strategy Intelligence third-domain proof

**Outcome:** a private, internal, decision-oriented domain establishes the third independent proof
and exercises authorized cross-domain consumption.

Corporate Strategy consumes only explicitly authorized Market and World projections, combines
them with internal objectives, initiatives, capabilities, assumptions, scenarios, and options,
and produces governed strategic-options Briefs. It must use the same substrate with no
strategy-specific lower-layer branch. The separate Corporate Strategy roadmap defines this gate.

### Platform P4 — Ontology Toolchain beta and generated SDK

**Outcome:** three-domain learning stabilizes authoring and consumption contracts.

Scope includes schema and deprecation policy, compiler migrations, activation lockfiles,
install/upgrade/rollback diagnostics, golden-fixture conformance, capability disclosure,
compatibility reports, JSON Schema/OpenAPI exports, and generated Python and TypeScript bindings
from compiled Pack IR. Overlay values never alter generated types. Generated clients use stable
resource APIs, never storage internals. Before clients may calculate Pack or Activation identities,
ACE must freeze a cross-language canonical-JSON specification and matched Python/TypeScript golden
vectors; alpha identity calculation remains compiler-owned.

### Platform P5 — Market Intelligence Solution beta

**Outcome:** deepen the first product only after the shared substrate survives P2 and P3.

Scope includes the public Market Pack, Overlay template, separately versioned source adapters,
semantic and structural strategy plugins where justified, Cases, Monitors, subscriptions, scoring,
suppression, multiple Brief templates, analyst workbench, generated SDK, public corpus, and
evaluations. This is the first point to migrate the broad legacy HTTP and UI surface.

Clean-install acceptance installs ACE plus the Solution Bundle, compiles the inert pack, binds
explicit adapters, previews and approves a public Overlay activation, and records the exact
Activation revision.

### Platform P6 — Kinetic ontology: governed actions and feedback

**Outcome:** approved intelligence can cause attributable effects without giving a pack authority.

- The pack declares action input, target, precondition, required authority, approval, adapter
  capability, result, and outcome schemas.
- Intelligence proposes and relates an action to exact intelligence.
- Core authorizes, persists, makes idempotent, executes, retries, and receipts it.
- A separately enabled adapter performs the external effect.
- Outcome feedback proposes a governed revision; it never rewrites prior evidence, Briefs,
  Decisions, policy, or receipts.

Acceptance covers denied authority, required approval, dry run, duplicates, retry, partial failure,
revocation, current-authority recheck on delivery, and material later use of an approved revision.

### Platform P7 — Data and deployment hardening

Initial support remains one ACE installation, one durable database, one application process plus the
bounded worker model, explicit local/package capability enablement, and proven restart, backup,
migration, and rollback. Warehouse/lakehouse parity, arbitrary ETL, streaming infrastructure,
distributed resolution, multi-region operation, fleet deployment, managed multi-tenant SaaS,
distributed approval, and exactly-once external effects are separate future programs.

An Apollo-like operator starts only after stable Activation semantics and three-domain proof.

## Release alignment

- **0.3.x:** P0 facades, boundary guards, and experimental contracts.
- **0.4.0:** governed Pack/Activation alpha plus P1 and World P2 proof.
- **0.5.0:** Corporate Strategy third-domain proof plus toolchain beta.
- **0.6.0:** kinetic action runtime, measured feedback/outcomes, and Market Solution beta.
- **0.7.0:** supported compiler, SDK, conformance, bundle, and three-domain platform promise.
- **0.8.0:** coherent analyst/workspace experience.
- **0.9.0:** collaborative and deployment hardening.
- **1.0.0:** stable Open Intelligence OS contract.

## Immediate dispatch

The completed P1A, P1B consumer, Market P1C1, Market P1C2, Market P1D1, and Market P1E packets provide the public-source
boundary, compiler-supported declarative mapping, direct public PREPARED interpretation, positive
and negative Market conformance inventory, exact Core-committed activation admission/reload, and a
digest-pinned consumer proof against Platform P1B's public durable PREPARED ledger. The proof admits
the existing price-move derivation atomically, records the exact route receipt, replays it through a
fresh service, fences historical and LIVE reads, and rejects every declared and host-boundary
negative without residue. P1C2 additionally binds one exact separately installed adapter wheel,
authenticated actor/product context, artifact-derived capability head, named current grant, and
named source definition to one deterministic no-network capture; Core atomically admits exactly one
LIVE Observation and exact-lineage Entity Snapshot with their acquisition/snapshot/admission
records, then replays the five identities through same and fresh services. Production SurrealDB
durability and actual public-evidence capture remain Platform/transport evidence rather than Market
claims. P1D1 adds the fresh revision-2 PREPARED route, governed Core reasoning, exact ordered
template/persona enforcement, one atomic Brief/synthesis append, revision-3 rollback, and exact
provider-free historical replay. The full expected public models and 18 negative cases are pinned
separately under release 0.4.0 while every historical 0.3.0 byte and identity remains frozen. P1E
adds a 0.5.0 inert decision-outcomes policy, exact Decision/no-action, later Outcome, bounded
feedback proposal, separate governed PREPARED state commit, exact replay, fresh-service reload, and
nine zero-residue negative cases while preserving every 0.4.0 module byte-for-byte.

P1D1 and P1E do not promote P1C2 LIVE material. P1E's Decision, Outcome, proposal, and policy state
are conformance-only PREPARED records and explicitly have no LIVE effect.

The paired **P1F LIVE intelligence bridge is verified** across Core and Market.

**P2 World Intelligence is no longer the next packet — it is substantially complete (2026-08-07).**
The broadly usable public showcase challenged those contracts with rapidly changing events,
attributed claims, independent and repeated sources, contradictions, corrections, semantic shifts,
and explicit uncertainty, and every World consumer contract request closed through domain-neutral
platform capability rather than through World semantics in a lower layer. P1F does not permit a LIVE
feedback claim, and no packet implies broad scheduling, delivery, autonomous promotion, political
persuasion, or an ACE-owned truth score. The separate
[World Intelligence roadmap](ace-world-intelligence-domain-roadmap-2026-08-06.md) defines that
domain boundary and acceptance sequence.

The remaining P2 work is narrow: acceptance-gate item 1 (committed activation lifecycle, upgrade,
and rollback), acceptance-gate item 6 (Market and World runtime co-activation isolation), a
separately reviewed opt-in network transport for the existing Federal Register adapter contract, and
World P2D LIVE multi-source conflict and correction. Of these, **gate item 6 is the one that
directly requires this repository**, because it must prove that a Market activation and a World
activation coexist at runtime without catalog, entity, persona, authority, or policy leakage.

Corporate Strategy Intelligence follows as the third-domain proof using private internal evidence
and cross-domain inputs; its roadmap status remains "implementation not started."

The legacy mixed Signal taxonomy, Market repository, routes, and UI remain compatibility inputs.
They do not become the new source of truth and must not be dual-written indefinitely.

## Roadmap rules

- A page rendering or plausible model output never completes a milestone.
- A live, durable, continuous, approved, delivered, or learned claim requires an exact receipt.
- Signal, Shift, and Brief form a derivation DAG, not a mandatory promotion workflow.
- Domain Packs are inert data; executable adapters, strategy plugins, general extensions, and
  Solution Bundles are different artifact and trust types.
- Packs and Overlays contain no credentials. Overlays cannot expand pack-declared capability or
  authority bounds.
- Pack installation is not compilation, activation, authorization, capability enablement, or
  execution.
- Every derived resource records the exact Domain Activation revision that governed it.
- A pack declares a verb; Intelligence may propose it; Core authorizes and receipts it; a bound
  adapter performs an approved external effect.
- Prepared fixtures never affect live counts, freshness, operational scoring, delivery, product
  outcome metrics, or LIVE learning. PREPARED conformance may record simulated Decision and Outcome
  material only when it remains separately labeled and has no LIVE effect.
- No migration deletes history before its replacement passes acceptance and the compatibility
  window is documented.
- The first domain proves the product, the second challenges the abstraction, and the third earns
  the platform claim.
