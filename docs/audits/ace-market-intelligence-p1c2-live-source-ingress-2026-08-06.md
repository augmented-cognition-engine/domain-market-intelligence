# ACE Market Intelligence P1C2 LIVE source ingress evidence

Date: 2026-08-06
Status: complete consumer conformance for the narrow deterministic LIVE path
Baseline HEAD: `3959e2f007cc266a2700cfe444567c44dfe7b3bd`

## Conclusion

Market P1C2 proves Sensing plus Core-governed admission for one deterministic public-product
payload:

```json
{"product_name":"Edge X1","listed_price":"1080.00","currency":"USD"}
```

The current ACTIVE Market activation, authenticated actor and product, artifact-derived capability
state, current named source-read grant, and exact mode-neutral source definition bind the separately
installed adapter artifact before capture. The adapter validates a deterministic injected transport
result without network access and produces only the canonical three-field payload. Core mints the
acquisition receipt, applies the frozen P1C1 mapping, and atomically admits exactly five LIVE records
in Platform order: acquisition, source snapshot, Observation, Entity Snapshot, and admission. Exact
same-service and fresh-service replay invoke the adapter once total.

The mapped entity attributes are exactly `name=Edge X1`, `price=1080.0`, and `currency=USD`. No LIVE
Signal, Shift, Brief, route, delivery, Decision, Outcome, feedback, learning event, schedule, monitor,
crawler, or source-discovery record exists.

## Exact reviewed artifacts

| Artifact | Path | SHA-256 | Status |
| --- | --- | --- | --- |
| ACE Core 0.3.0 | `/tmp/ace-p1c2-final-hardened-019fd828/work/dist/ace_core-0.3.0-py3-none-any.whl` | `902e52ffd3c5850aadd9b1b1cb69f190a8c6d0f93c288bb229d2b1c1e7077f10` | reviewed dependency |
| public-product adapter 0.1.1 | `/private/tmp/ace-market-p1c2-adapter-dist-v011.9Zurbf/ace_market_public_product_source-0.1.1-py3-none-any.whl` | `6e1cc3c710e7a1e9d8d464a356cadb1c41ea5663dacf57041943456594671c99` | final frozen adapter |
| Market root 0.1.0 | `/private/tmp/ace-market-p1c2-clean-source-build.NyyXRz/dist/ace_ext_b2b_marketing-0.1.0-py3-none-any.whl` | `7fe14c054635a9cd9cbdcf5e6fde4b5d5edf5ee4b4d993b787e5b801b5ad0c46` | final P1C2 consumer wheel |
| public-product adapter 0.1.0 | `/private/tmp/ace-market-p1c2-adapter-dist.jDo4IJ/ace_market_public_product_source-0.1.0-py3-none-any.whl` | `da6ea87cf5b74f9c372527682ddbd53dc07decffbf1e1fa973609ab57f9c949a` | superseded evidence only |

Adapter v0.1.1 owns and persists the exact extraction locator
`json-pointer:/listed_price`; a different transport locator fails closed. Its two installed package
members are byte-identical to the frozen source: `ace_market_public_product_source/__init__.py`
hashes to `88caf7dd41eaafcb321c67f427cd04d56255440ac2e3d97e588f0aa320d8c37c`,
and `adapter.py` hashes to
`c16ed61d9ee8bf56ec8d16c9989410b55867c3df6b994a03db060c7d91f6f6b3`.

The adapter has no `ace.extensions` entry point and supplies no network client. The root Market wheel
contains 85 files, no `ace_market_public_product_source` member, and only this extension entry point:

```text
b2b_marketing = ace_ext_b2b_marketing.marketing_extension:MarketingExtension
```

## Frozen Pack and P1C1 truth

P1C2 did not modify the Pack manifest or source-mapping module. The exact frozen bytes remain:

| Pin | SHA-256 |
| --- | --- |
| `manifest.json` | `82719602adf0ddd47ab1d7e80e9806c94c9c329705acc61c283796d79bcbd46d` |
| `modules/source_mapping.json` | `acebb1a048ca284c9d7d902e4c1a3af9ea02567f13836685382a02047e7ee293` |
| P1C1 conformance manifest | `bf65b0d44622c33411bc2911bd765095e20c38db3aa3564652391aedf0889ced` |
| public-product boundary | `dfc0a63eaaebca857c46da62080ae14f5d46793d808fe0296d66c951c55bdff5` |
| PREPARED golden | `5d04afed27b785f35cbd29083d566bb84770a2fbdf4a44837ea196e432dd1cdf` |
| PREPARED negative cases | `39003bb393dc94bf2737b7568993577a0e9b55a4efc7981922270350a2e8095c` |
| durable PREPARED expected | `735fe7aa0dc1678daa3dec3d052317452314b075c45ef24b88d8d409d131b6b7` |

The compiled Pack remains `pack_ir:19de6d59b28095f7bd7600364c3b4de7` with digest
`sha256:19de6d59b28095f7bd7600364c3b4de787cce0365764cf54ab9f282f3412c2dd`.
The source-mapping module digest remains
`sha256:74b631b62884f99301b60325e2ee1ada7a130f57b9c55a3397a0dd9252bc7226`,
and `product_price_snapshot` remains
`sha256:ed421cef871bc9467fee82bd1168bbd66bab9b7c05c3477d8ba795e18d913c96`.
Its declared transforms remain bounded copy from `/product_name` to `name`,
`decimal_text_to_number` from `/listed_price` to `price`, and exact three-character ASCII-uppercase
copy from `/currency` to `currency`. P1C1 PREPARED outputs and their record space remain unchanged.

## Final P1C2 pins

The separately pinned LIVE conformance artifacts are:

| Artifact | SHA-256 |
| --- | --- |
| `p1c2_live_source_input.json` | `555b7a2e41c5864038a357edcafebeb73187339dbb1fdeff5c8c03da93a659e2` |
| `p1c2_live_source_negative_cases.json` | `bbd89f833094605821a164b56da0cf1a97663d9ea26e4b09a9c73d91bd5e820f` |
| `p1c2_live_expected.json` | `3d44cf54294b3fb53b1d14503730894050d38e124fdf5422412d9010254ca254` |
| `p1c2_live_manifest.json` | `b3ab83ab4d32df2c1211802a126d39e3165fc2545e0c4e7e7112adf95ce94722` |

The exact identity chain is:

| Resource | Identity / digest |
| --- | --- |
| Activation | `domain_activation:b50f9dd61d6299362f64ddac9e0bb284` |
| Activation spec | `activation_spec:e6624655da41664463fd4571cd6271b6` / `e6624655da41664463fd4571cd6271b665517f9f6523dcdf2957a1db5070c5c0` |
| Activation revision | `activation_revision:ba6d851d20dd730bb88496a85d041402` / `sha256:ba6d851d20dd730bb88496a85d0414023b09c1cecbe7a62fe1b28fc61fdc8398` |
| Activation commit | `governed_state_commit:7806c857308a55a19acd90316d3e6b60` / `7806c857308a55a19acd90316d3e6b60ad7f4c170d4424c4e939de9945d047fa` |
| Ingress request | `live_source_ingress_request:22299ec035e6f29bc3230509782332c3` / `sha256:22299ec035e6f29bc3230509782332c37ae0a59b41cf440031aabadc4d9ec531` |
| Capability state | `capability_state:330bb7abf744dcc4bc8ec67354750512` |
| Capability-use receipt | `capability_use_receipt:8d1f45642136671254154f0bbc39b25f` / `sha256:8d1f45642136671254154f0bbc39b25f45426778ccdc183b9ecb4f98106294de` |
| Authority-use receipt | `authority_use_receipt:4f7c273102fd04e49c62d9f7766060d1` / `sha256:4f7c273102fd04e49c62d9f7766060d1644b144aed83dc48726d6f0ad33c1f46` |
| Acquisition receipt | `source_acquisition_receipt:dc005682ac4f94ad82f1dcde35e52878` / `sha256:dc005682ac4f94ad82f1dcde35e5287872d0ac8fcefc44f58b0a4b47d3a83851` |
| Source snapshot | `source_snapshot:a44c8811b2888873d3f25d835e2d4b2c` / `sha256:a44c8811b2888873d3f25d835e2d4b2c0ff55fc2a7fbf81a2f63b6337fcae4b6` |
| Observation | `observation:0bbe3d54ef0b92028552f1d21c503c5c` / `sha256:0bbe3d54ef0b92028552f1d21c503c5c38402f09b6af6e03af922d58cd088372` |
| Entity Snapshot | `entity_snapshot:a3e2583016c2fd4688504a2ab0b7f2b7` / `sha256:a3e2583016c2fd4688504a2ab0b7f2b7701c96c9ed0c39ddecc6b0cb34c04d49` |
| Admission receipt | `live_source_admission_receipt:9e93748ca854e00ff81e7bdb3cd29ee3` / `sha256:9e93748ca854e00ff81e7bdb3cd29ee3a89d1cbc253b518b25bf7d3f7f774da7` |
| Atomic transaction | `append_only_transaction:3783cc16bb4e1bb2d8ce205064acee34` |
| Transaction receipt | `append_only_receipt:3783cc16bb4e1bb2d8ce205064acee34` / `sha256:a72a894fbee1745224fd68b251786d47ca429c6950cc42a9d5607b539164df14` |

The committed activation still reports `live_authority=false`; authority to perform this one capture
comes only from the authenticated use-time capability and actor-scoped grant receipts.

## Adversarial and replay evidence

The exact 41-case LIVE negative inventory is unique and exactly equals the exercised case-ID set.
It covers artifact ID/version/digest mismatch before invocation; wrong actor, product, source,
configuration, grant, expiry, revocation, and unrelated capability head; all four governed-head
changes during capture; HTTP/userinfo/fragment/local/private URI policy; non-global address,
redirect, source type, effective URI, DNS binding and exact locator failures; malformed, oversized,
duplicate, missing-field, type-smuggled, and unfaithful payloads; impossible observation/capture
ordering; a grant expiring during capture; forged request/result/receipt; PREPARED relabeling;
idempotency conflict; interrupted persistence; and cross-product replay.

The decimal string `9007199254740993` passes adapter extraction but fails the P1C1
`decimal_text_to_number` mapping as not faithfully representable as a JSON number. Every rejected
new admission leaves zero LIVE records and zero receipt. An injected interruption after three
candidate records also leaves no residue. Exact replay returns the same five identities without a
second adapter call; historical replay survives later activation, capability, grant, and source
changes; cross-product read/replay fails. A shared test store retains eight PREPARED records and five
LIVE records in isolated record spaces.

## Clean installed-wheel proof

The external bootstrap sequence was explicit and ordered:

1. Hash all three wheel files before installing or importing them.
2. Copy a dependency-complete Python 3.12 environment to the disposable directory
   `/private/tmp/ace-market-p1c2-clean-bootstrap.qPYVSx`.
3. Force-install only the exact Core and Market wheels with no dependency resolution.
4. Run isolated Python (`-I`) and prove the adapter import is absent, the installed Pack compiles to
   the frozen IR, and the Market distribution contains no adapter member or entry point.
5. Install the exact adapter wheel with no dependency resolution.
6. Run the mandatory-wheel acceptance command in isolated Python with all three wheel paths and the
   exact Market wheel hash.

The final Market wheel was built in a fresh temporary source/build directory, not a reused
`build/lib`. Before its wheel hash was frozen, every JSON member under
`domain_packs/market_intelligence/` was byte-compared with current source. The acceptance command
validated each local `direct_url.json` path and recorded archive SHA-256 against the supplied wheel,
resolved the imported/resource path to the exact distribution-owned RECORD entry, required a
SHA-256 RECORD hash, encoded the installed digest in the RECORD's URL-safe base64 form, and compared
the two values. Verified installed-file SHA-256 values were:

- Core `ace/__init__.py`: `8ed1170b207a3c7b6df6a03e3dd413c44593542a24d45f537a329baa218d9955`
- adapter `ace_market_public_product_source/__init__.py`:
  `88caf7dd41eaafcb321c67f427cd04d56255440ac2e3d97e588f0aa320d8c37c`
- Market `domain_packs/market_intelligence/manifest.json`:
  `82719602adf0ddd47ab1d7e80e9806c94c9c329705acc61c283796d79bcbd46d`

No editable or arbitrary imported package can satisfy this artifact-bound command while claiming
the reviewed wheel identities.

## Verification record

- adapter unit/adversarial suite: 33 passed
- adapter plus P1C2 LIVE source suite: 77 passed, 1 artifact-bootstrap test skipped
- adapter plus P1C1 Pack/durable plus P1C2 LIVE focused suite: 104 passed, 1 artifact-bootstrap test skipped
- disposable clean-install artifact-bound CLI positive/tamper test: 1 passed, 44 deselected
- clean installed Core + Market Pack compile with adapter absent: passed
- clean installed Core + adapter + Market mandatory-wheel acceptance: passed
- repository Ruff check: passed
- focused Ruff format check: passed
- `git diff --check`: passed
- final full non-provider Python suite, collected from
  `ace_ext_b2b_marketing/tests`, `domain_packs/tests`, and
  `adapters/public_product_source/tests`, and run with `ACE_DISABLE_EXTENSIONS=1` and
  `-m "not e2e and not requires_extensions"`: 542 passed, 12 skipped, 35 deselected
- an earlier full ordering exposed `test_three_new_instruments_are_registered`: it passes alone and
  reproducibly fails after `test_instrument_registry.py`, demonstrating a pre-existing global
  instrument-registry provenance/order leak outside P1C2; no P1C2 change masks or fixes it, and the
  final full ordering completed green

Provider-bound E2E tests were deliberately deselected; this packet performs no network access and
does not claim provider or public-endpoint evidence.

## Baseline-relative file manifest

The starting worktree was intentionally very dirty. Its file-level status and hashes were captured
in the task execution record before editing; this package does not ship a separate full-worktree
baseline snapshot. The table below is the persistent baseline-relative manifest for this packet.
No unrelated baseline path was modified by P1C2. The exact P1C2 edit set is:

| Path | Baseline-relative action |
| --- | --- |
| `README.md` | reconciled P1C2 status and packaging/network limits |
| `pyproject.toml` | dependency/package-boundary comment only |
| `adapters/public_product_source/pyproject.toml` | added separate adapter distribution |
| `adapters/public_product_source/README.md` | added adapter trust/network/locator contract |
| `adapters/public_product_source/src/ace_market_public_product_source/__init__.py` | added public adapter API |
| `adapters/public_product_source/src/ace_market_public_product_source/adapter.py` | added bounded source-specific adapter |
| `adapters/public_product_source/tests/test_public_product_source_adapter.py` | added no-network adapter conformance |
| `domain_packs/market_intelligence/conformance/p1c2_live_source_input.json` | added exact LIVE input |
| `domain_packs/market_intelligence/conformance/p1c2_live_source_negative_cases.json` | added exact 41-case negative inventory |
| `domain_packs/market_intelligence/conformance/p1c2_live_expected.json` | added exact LIVE identities |
| `domain_packs/market_intelligence/conformance/p1c2_live_manifest.json` | added separate LIVE artifact manifest |
| `domain_packs/tests/test_market_intelligence_pack.py` | excluded separately governed LIVE files from the frozen PREPARED inventory only |
| `domain_packs/tests/test_market_intelligence_live_source_conformance.py` | added host and adversarial conformance |
| `scripts/p1c2_live_public_source_acceptance.py` | added deterministic acceptance and exact installed-wheel proof |
| `docs/ace-market-intelligence-extension-roadmap-2026-08-05.md` | reconciled completion and next gate |
| `docs/ace-market-intelligence-public-extension-pivot-2026-08-05.md` | reconciled completion and next gate |
| `docs/audits/ace-market-intelligence-p1c2-live-source-ingress-2026-08-06.md` | added this evidence record |

`domain_packs/market_intelligence/manifest.json`,
`domain_packs/market_intelligence/modules/source_mapping.json`, and legacy
`ace_ext_b2b_marketing/marketing/source_ingestion.py` were not modified by this packet.

## Guarantee, limitation, and next dependency

This guarantees one narrow Market LIVE runtime-conformance path against the exact reviewed Core,
adapter, and Market artifacts. It proves authenticated, actor/product-scoped, current governed use;
bounded deterministic extraction; Core acquisition provenance; pure frozen mapping; atomic
five-record admission; fail-closed adversarial handling; exact replay; and PREPARED/LIVE isolation.

It does not prove captured public evidence. `https://public.example.test/products/edge-x1` is an
unreachable fixture URI. Actual capture remains gated on an explicitly authorized stable endpoint
and a reviewed transport that denies credentials and redirects and validates every resolved and
connected address throughout use against DNS rebinding. It does not promote the LIVE Observation
into a Shift or Signal, reason or enforce a Brief template, take a Decision, record an Outcome,
deliver externally, monitor, discover sources, or learn.

The precise next packet is Platform P1D1: governed PREPARED, route-triggered exact-context Core
reasoning and template-enforced Brief assembly using the existing P1B route receipt. P1C2's single
LIVE Observation has no LIVE baseline, Shift, Signal, or route; LIVE Shift/Signal/routing therefore
remains a separate future bridge required before any LIVE Brief. P1E Decision → Outcome → governed
feedback remains open after P1D1.
