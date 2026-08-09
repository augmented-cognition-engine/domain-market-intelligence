# Market P1C1 — public source-mapping consumer evidence

**Date:** 2026-08-06
**Status:** complete against the exact unreleased Platform P1C1 wheel
**Scope:** JSON-only, PREPARED-only Market consumer proof; Platform P1C2 remains open

## Dependency gate

The required wheel was verified before editing:

```text
/tmp/ace-p1c1-final2.R17g1f/ace_core-0.3.0-py3-none-any.whl
sha256:07f5134488f7de16800aae290bb05284fdffe8fb679353b0b3f9771630ad302c
```

With that wheel first on the import path, `ace`, `ace.core`, `ace.intelligence`, and `ace.testing`
all resolved directly from the wheel. The public surface included
`CanonicalSourceSnapshotV1Alpha1`, `SourceAcquisitionMode`, `SourceMappingModuleV1`,
`ResolvedSubjectBindingV1Alpha1`, `interpret_prepared_source_mapping`, and the optional testing
conformance seam. No `core.engine`, `core`, or private `ace._*` import is used by the Market pack
tests.

## Consumer migration

Pack v0.3 adds `modules/source_mapping.json` as an inert
`ace.intelligence.source-mapping/v1alpha1` module depending on `market_ontology`. Its one rule:

- binds `source_definition:public-northstar-edge-x1` and `public_product_page`;
- requires `public_product_snapshot` and `read_public_product_source`;
- permits HTTPS only and consumes the already-resolved `listed_product` subject as `product`;
- copies `/product_name` to `name` with length 1–256;
- converts `/listed_price` to `price` with `decimal_text_to_number`;
- copies `/currency` to `currency` with exact length 3 and `ascii_upper`; and
- assigns static confidence 1.0.

`AttributeMappingV1` has no numeric min/max declaration. The public interpreter instead enforces
bounded decimal text, faithful finite JSON-number representation, and compatibility with the
ontology `number` target. Market adds no private numeric interpreter rule.

The source-definition identity is deliberately mode-neutral. It describes the exact source;
PREPARED versus LIVE belongs to acquisition and admission mode. This lets P1C2 reuse the exact
mapping without forking source identity while leaving every P1C1 resource PREPARED-only.

The old fixture-local validator and hand-built Observation/Entity Snapshot normalizer were removed.
The consumer now constructs `CanonicalSourceSnapshotV1Alpha1` from the captured payload, lets Core
derive `source_snapshot_ref` and `source_snapshot_digest`, constructs
`ResolvedSubjectBindingV1Alpha1`, and calls `interpret_prepared_source_mapping` directly. Legacy
fixture `source_snapshot_ref` and ambiguous `source_digest` inputs were removed; the payload digest
is now explicitly `captured_payload_digest`. The nested fixture acquisition receipt was also
removed. Only its reference and digest cross the public contract as PREPARED provenance, without a
claim of live acquisition success.

The mapping produces only the product Observation and product Entity Snapshot. Competitor and
relationship context is separate fixture setup and is never attributed to source mapping. The
downstream proof remains unchanged semantically: 1200 becomes 1080, absolute change is -120,
percent change is -10%, currency and source URI are unchanged, and the Brief cites both exact Core
source snapshots.

## Deterministic pins

| Artifact | Exact identity / digest |
|---|---|
| Compiled pack | `pack_ir:19de6d59b28095f7bd7600364c3b4de7` / `sha256:19de6d59b28095f7bd7600364c3b4de787cce0365764cf54ab9f282f3412c2dd` |
| Mapping module | `market_source_mapping` / `sha256:74b631b62884f99301b60325e2ee1ada7a130f57b9c55a3397a0dd9252bc7226` |
| Mapping rule | `product_price_snapshot` / `sha256:ed421cef871bc9467fee82bd1168bbd66bab9b7c05c3477d8ba795e18d913c96` |
| Overlay | `overlay_ir:0cb0ba28f522efd70a811d154aad0e2d` / `sha256:0cb0ba28f522efd70a811d154aad0e2da7a496daa8019ebb7ac22b6129ea3219` |
| Activation spec | `activation_spec:66c79014c7a04dd082b949d1e49cfb42` / `66c79014c7a04dd082b949d1e49cfb42a2d2d9b5e51448c57781bc482ea4f9f5` |
| Activation revision | `activation_revision:a6ee050fb15d6bb1c4d2cbade4111a40` / `sha256:a6ee050fb15d6bb1c4d2cbade4111a40b60e1e3b2a235f89b421cfccf45de0a1` |
| Source snapshots | `source_snapshot:79e9d6d28cb58b3477d91fa176f172ff`, `source_snapshot:1293d090b0a2907907d1bb32bf0ac825` |
| Observations | `observation:1a94c2ec8cd09ca430c3bad2f5ae4dc5`, `observation:d489523455c199ca3fc6b9dadc479dcb` |
| Entity Snapshots | `entity_snapshot:0707caf19410b77f57b695ddc839101a`, `entity_snapshot:84f46bc741de75c4b12367f09cc31e3f` |
| Shift / Signal / Brief | `shift:08105b9811c0a990fcc7fbd4f4c96cce`, `signal:7c494d503e72fa73c070c8b9b5e3510e`, `brief:1bf59d3e6c5a47634c345a9366b555be` |
| Core commit | `governed_state_commit:e47badabd5229721630c514be7a2b888` / `e47badabd5229721630c514be7a2b8886e90d706bc58c519880f5dd57b62771c` |
| Durable batch | `resource_admission:760643dcee0649ab646639e9dfcfbb74` / `sha256:caf1c969dfb3b205c1d02ee85b76df3f88a578af73c1fca36aebd5f0f0f371f9` |
| Transaction / receipt | `append_only_transaction:f2bf4033973370e4fd951db078757aae` / `append_only_receipt:f2bf4033973370e4fd951db078757aae` |
| Route receipt | `attention_disposition:9e84c24f2742325d5496a98b43c7545a` / `sha256:9e84c24f2742325d5496a98b43c7545a42e5ad6fd728671a9f32a98c36c189ae` |

The durable expected artifact additionally pins transaction hashes, every immutable storage ID and
material hash, historical visibility, processing order, and route material.

## Verification record

- Focused pack and durable conformance: **27 passed**.
- Broader Market Python suite, excluding E2E and extension-required tests: **465 passed, 11 skipped,
  35 deselected**.
- The previously reported order-dependent instrument-registry failure did **not** reproduce in this
  run; no registry code was changed.
- Repository Market Ruff lint: **passed**.
- Focused Ruff format check: **passed**.
- `git diff --check`: **passed**.
- All **11** packaged Market files parse as JSON; manifest resource and conformance digests match
  exact bytes; the pack contains no non-JSON file.
- Static import scan: no private Platform import.

Conformance artifact hashes:

```text
pack manifest       82719602adf0ddd47ab1d7e80e9806c94c9c329705acc61c283796d79bcbd46d
source mapping      acebb1a048ca284c9d7d902e4c1a3af9ea02567f13836685382a02047e7ee293
conformance manifest bf65b0d44622c33411bc2911bd765095e20c38db3aa3564652391aedf0889ced
source boundary     dfc0a63eaaebca857c46da62080ae14f5d46793d808fe0296d66c951c55bdff5
golden fixture      5d04afed27b785f35cbd29083d566bb84770a2fbdf4a44837ea196e432dd1cdf
negative vectors    39003bb393dc94bf2737b7568993577a0e9b55a4efc7981922270350a2e8095c
durable expected    735fe7aa0dc1678daa3dec3d052317452314b075c45ef24b88d8d409d131b6b7
```

## Wheel and clean-install acceptance

The extension wheel built successfully:

```text
/tmp/ace-market-p1c1-dist.dXZnCt/ace_ext_b2b_marketing-0.1.0-py3-none-any.whl
sha256:ace4f99cc542dd0dbb4959a9bdbb7e6cfaa9e0e16655c068efd09d0e5b8ccbe9
```

Wheel inspection found the pack manifest, five modules, and five conformance artifacts, including
`source_mapping.json`, and found no pack tests, bytecode, cache, or build paths. In a fresh virtual
environment, Core and Market were installed from only the two exact local wheel paths with
`--no-deps`; generic Pydantic/Pytest dependencies were then installed separately. Distribution
metadata recorded both exact local origins. `ace.core`, `ace.intelligence`, and `ace.testing`
resolved under the clean environment's `site-packages`; the installed Market pack compiled to the
pinned pack identity; the installed mapping bytes retained SHA-256
`acebb1a048ca284c9d7d902e4c1a3af9ea02567f13836685382a02047e7ee293`; and the clean interpreter
again passed all **27** focused tests.

## Remaining P1C2 boundary

P1C1 performs no I/O, network access, secret lookup, persistence addition, live grant resolution,
adapter execution, or LIVE admission. P1C2 remains responsible for a new narrow separately packaged
adapter behind Platform's future live-ingress seam, exact use-time activation/capability/grant
binding, capture, acquisition-receipt resolution, and LIVE admission. The existing
`ace_ext_b2b_marketing/marketing/source_ingestion.py` module is legacy compatibility code with
caller-supplied URLs, broader transport behavior, its own clock/result model, and no exact
activation/capability/grant/receipt binding. It is explicitly not the future live adapter.
