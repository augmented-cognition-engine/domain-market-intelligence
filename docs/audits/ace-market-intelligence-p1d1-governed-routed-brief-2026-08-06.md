# ACE Market Intelligence P1D1 governed routed Brief evidence

Date: 2026-08-06
Status: complete consumer conformance for the narrow PREPARED route-triggered Brief path

## Conclusion

Market P1D1 consumes the canonical Platform P1D1 public API to turn one fresh routed PREPARED
price-move closure into one governed, reasoned, template-enforced Brief. The Domain Pack remains
inert JSON. This repository adds no provider, connector, persistence implementation, reasoning
loop, private Core import, delivery path, or imperative pack control flow.

The historical Market 0.3.0 root remains a byte-frozen archive. Its Pack IR remains
`pack_ir:19de6d59b28095f7bd7600364c3b4de7` with digest
`sha256:19de6d59b28095f7bd7600364c3b4de787cce0365764cf54ab9f282f3412c2dd`,
and its synthesis module remains
`sha256:99ccea5e5fe93cd2ad22c20e9a36d30ce61506f8f998bc30da1a0432947495c0`.
The historical manually authored P1B Brief remains
`brief:1bf59d3e6c5a47634c345a9366b555be` /
`sha256:1bf59d3e6c5a47634c345a9366b555be04e45f3ab2f8099d54b998cef4c6d5b8`
and is readable after rollback.

The additive Market 0.4.0 release retains `pack_id=market_intelligence` and every existing module,
detector, template, route, and persona ID. Ontology, source mapping, detection, and personas are
byte-identical to 0.3.0. Only synthesis opts into
`ace.intelligence.synthesis/v1alpha2`, whose ordered sections are:

```text
what_changed → why_it_matters → recommendation → limitations
```

## Exact reviewed artifacts

| Artifact | Path | SHA-256 |
| --- | --- | --- |
| canonical ACE Core 0.3.0 | `/private/tmp/ace-p1d1-canonical-final.AujpoF/ace_core-0.3.0-py3-none-any.whl` | `267cfed8ec3057439abf2a55e4f595e34c92f3b10f4e37c21a2e253a80b9dc4d` |
| final canonical Market 0.1.0 wheel | `/private/tmp/ace-market-p1d1-canonical-final.8fBD9c/ace_ext_b2b_marketing-0.1.0-py3-none-any.whl` | `895c2b0cbc975bfb264ebe8a48fe93280440019f8d6a993af81fa2de45f6134b` |
| Market 0.4.0 manifest | `domain_packs/market_intelligence/releases/v0_4_0/manifest.json` | `6f24562e0e9a3fe1959c7c1db7f736bd130d8a1da5694d0c7cd8e9a62047cdea` |
| P1D1 input | `releases/v0_4_0/conformance/p1d1_prepared_brief_input.json` | `0763bab7ff71b7dcb5eca91788ff8377ff109d64c1f730b9e793624a62d7b53a` |
| P1D1 expected | `releases/v0_4_0/conformance/p1d1_prepared_brief_expected.json` | `744323b07dceee2cc50d7c7e88884af56381516793e1d48b7b8a4499b4553e13` |
| P1D1 negative cases | `releases/v0_4_0/conformance/p1d1_prepared_brief_negative_cases.json` | `cf6f3e851620a557be2835dadd286f26f21d3de4c7a1951a12323c210acaae42` |
| P1D1 manifest | `releases/v0_4_0/conformance/p1d1_prepared_brief_manifest.json` | `f4e35732ce7431993f7c20f7c8b883dc72995eed6f52a94215b124f06b937f24` |

The compiled 0.4.0 Pack is `pack_ir:c87b61600105da2a72d6d7a9fa7cb7dd` with digest
`sha256:c87b61600105da2a72d6d7a9fa7cb7dde2fd6edbc0e63327c541b80a96dcd66c`.
Its synthesis source hashes to
`2a18ca17378d509a73fe748fd4c9441f3e668ffb85d7daa710c033bd7dbbfa4a`,
the compiled synthesis module to
`sha256:fa6346a4173b7bbae1cd62a06a51b1a184f8408160deebfd95b71b0dfe3f0512`,
and the resolved `competitive_price_move_brief` template to
`sha256:f960449b8ca85a1be41d2d800198e1f6b5c4d5f14a87c00dc55099f8eedcdc91`.
The exact persona is `competitive_intelligence_analyst`.

## Activation and rollback lifecycle

The logical activation remains
`domain_activation:fc68e4ee0ce4b6b35829fd584452487f` across all three append-only revisions:

| Revision | Revision ID / hash | Commit ID / hash |
| --- | --- | --- |
| 1 — exact 0.3.0 | `activation_revision:a6ee050fb15d6bb1c4d2cbade4111a40` / `a6ee050fb15d6bb1c4d2cbade4111a40b60e1e3b2a235f89b421cfccf45de0a1` | `governed_state_commit:e47badabd5229721630c514be7a2b888` / `e47badabd5229721630c514be7a2b8886e90d706bc58c519880f5dd57b62771c` |
| 2 — exact 0.4.0 | `activation_revision:394d4709a59d74c06a826e9726baa78d` / `394d4709a59d74c06a826e9726baa78d8cb060457d024ddcfe5b581ecba2aec3` | `governed_state_commit:1abbe4bc2cc228e1846e70c108704d25` / `1abbe4bc2cc228e1846e70c108704d25765fa5cf7866acb4b94ec9d30f0c8275` |
| 3 — rollback to exact revision-1 spec | `activation_revision:7cc5b971eaa98e5effcb32bb6eb54382` / `7cc5b971eaa98e5effcb32bb6eb543829c725f65e5e4e15e77163feb6d36e0ca` | `governed_state_commit:481ad7dd9513ad3f9483fa9bfd794dbe` / `481ad7dd9513ad3f9483fa9bfd794dbe747ab25609e7b1ef17d9e7303cf7db9b` |

Revision 2 points to revision 1 as `prior_revision_id`. Revision 3 points to revision 2 as prior,
names revision 1 as the rollback target, and restores the exact revision-1 activation spec. The
resolver retains the exact compiled 0.3.0 and 0.4.0 Packs. After revision 3 becomes current, a fresh
service configured with current 0.3.0 replays the historical revision-2 synthesis provider-free.

## Fresh routed PREPARED closure

The new immutable derivation key is
`derivation:market-intelligence:p1d1:prepared-price-move:v1`. Its batch is
`resource_admission:f82cb0ea68f151cb542be9c7924af13f` /
`sha256:ee91a74b02988885aff7d98992d5d7d529456e173f92a35767395e3c7e1f6bf7`.
It contains exactly two Observations, two Entity Snapshots, one Shift, and one Signal, in that
deterministic admission order; `brief` is null.

| Resource | Exact identity / digest |
| --- | --- |
| baseline Observation | `observation:e041e86159bb12d9283ba960650cb2ae` / `sha256:e041e86159bb12d9283ba960650cb2aeea539d7c4b8e7b887d63b535bc77b888` |
| current Observation | `observation:578cb5c4864ddeb9188f6542fffd810d` / `sha256:578cb5c4864ddeb9188f6542fffd810d3c1143e550d5f42d9b96715a04cc74b9` |
| baseline Entity Snapshot | `entity_snapshot:81537a4fe7311b74d65288b71687c0e2` / `sha256:81537a4fe7311b74d65288b71687c0e2e793f0ce2816361ca3dc0efbf2549df0` |
| current Entity Snapshot | `entity_snapshot:a61f50d081413e0dcc1a3f9b1818869a` / `sha256:a61f50d081413e0dcc1a3f9b1818869a91d5596cb8c4be2c56d9952f76c08fc1` |
| Shift | `shift:03fa1009f3b5a7e7f6946b427d19dca5` / `sha256:03fa1009f3b5a7e7f6946b427d19dca5a65baedec3c0d31fb3aeda086cd8e289` |
| Signal | `signal:2c8ecb8c4d72f4883d86776d57dbb952` / `sha256:2c8ecb8c4d72f4883d86776d57dbb9523136a3fdad8e19f86b5453ede7f0a438` |

The fresh route receipt is `attention_disposition:ff361fe988c11b1e4aca5398fd99a60a` /
`sha256:ff361fe988c11b1e4aca5398fd99a60a2133229e7931ef7011f9ad55100642e8`.
The seven-record closure-plus-attention transaction is
`append_only_transaction:5e76f0e2cbff318e08ab4f3d334470a1`; its receipt is
`append_only_receipt:5e76f0e2cbff318e08ab4f3d334470a1` with hash
`sha256:5f898dbbcce3eb6c7b6192c394ecfb0faf29a467a83710650fa5aeb4a8a6f02d`.
The historical P1B attention receipt is retained only for readability and the old-attention
negative case; it is not reused as the P1D1 positive route.

## Governed reasoning and exact Brief

The public synthesis request is
`brief_synthesis_request:611ddbc63fe22ef0fcfa28c082266221` /
`sha256:611ddbc63fe22ef0fcfa28c08226622141b42fdc828051c825c4feea6c8fdd76`.
Its public governed reasoning references are:

- request `governed_reasoning_request:8c68bf57318f224ce9df52473722bf92` /
  `sha256:8c68bf57318f224ce9df52473722bf92752ee4a045cde62c436c794b1bce06af`;
- structured result `structured_final_result:9f676a47df0d1c467c01463c3fa4748d` /
  `sha256:9f676a47df0d1c467c01463c3fa4748d2a93ee9fdf976956f0aba79aa12c5e44`;
- terminal receipt `reasoning_terminal:cfdb23cd17d708b2911699f88afd25b2` /
  `sha256:cfdb23cd17d708b2911699f88afd25b28ad0c241487421c070d449c1072c34d9`.

The result is `brief:c65102850e3d543713a0ff71d02dcc78` /
`sha256:c65102850e3d543713a0ff71d02dcc7803d0255bcc116abb6caafdbab307dff5`
with canonical title `Competitive Price Move Brief`. It contains exactly one Recommendation section.
Its exact cited assertion is:

> The listed Edge X1 price changed from USD 1,200 to USD 1,080.

The two citation IDs are `citation:08b85552c86d7738f7103dc11ca6207b` and
`citation:126dd510c8001d7df6da542a90c8094c`; both final `locator` and `excerpt` fields are null. The
cited claim binds only the two exact Observation supports. The inference claims bind the two Entity
Snapshots, Shift, and Signal exactly as frozen in the expected artifact. All six selected context
records are used.

No `competitor` or `makes` relationship is persisted in the selected closure. Consequently,
`Northstar` is absent from the entire serialized Brief, including title, summary, body, claims, and
citations—not merely the primary statement. The Brief explicitly says:

> Ownership, motive, and market effect are not established.

The synthesis receipt is `brief_synthesis_receipt:e60876278f68e31e7941381f29741b8f` /
`sha256:e60876278f68e31e7941381f29741b8fde840c53d50689d0b43a01b6fdc59d71`.
The atomic Brief-plus-synthesis transaction is
`append_only_transaction:9519bd315fbe1d4b8593970a972f0f69`; receipt
`append_only_receipt:9519bd315fbe1d4b8593970a972f0f69` has hash
`sha256:90a9ad4dd96e49ab564493a46851460d80bd796d8b6d0b88c4a4f04436594fca`.
The exact append request hash is
`sha256:23ab5cc618d85d83b1d7ea01c957247a03ecd452627edea0357b1043cf184f96`.

First synthesis invokes the provider once. Same-service replay is exact and adds no invocation.
Fresh-service historical replay after rollback is also exact and invokes a forbidden-provider test
double zero times. No delivery authority is resolved or granted. All P1D1 resources are PREPARED;
all LIVE counts remain zero.

## Fail-closed inventory

The exact 18-case inventory covers:

- old attention identity and independently wrong attention digest;
- a derivation containing a prebuilt Brief;
- wrong Pack version, activation revision, derivation key, as-of, and cutoff before Signal
  availability;
- wrong provider Brief type and persona;
- missing and reordered required sections;
- a cited claim supported by a non-Observation;
- unknown support and unused selected support;
- divergent replay under the same synthesis key;
- a resolver returning the wrong historical Pack; and
- a missing historical Pack.

Each case pins the public error type/message, safe public cause where present, and provider-call
count. Every failed attempt pins deltas of zero for newly created Brief records,
brief-synthesis-receipt records, and PREPARED transaction receipts whose key begins
`brief_synthesis:`. Provider-output policy failures may legitimately retain governed-reasoning
transactions; the no-residue assertion is deliberately scoped to downstream PREPARED synthesis.

## Clean installed-wheel proof

The final wheel was built from a fresh temporary source copy with build, dist, cache, Vite, Git,
and Node output excluded. The dependency-complete Python environment was copied to
`/private/tmp/ace-market-p1d1-final-artifact.KpN1MF/clean-venv`, then exact Core and Market wheels
were force-installed without dependency resolution.

Every origin probe ran with `PYTHONPATH` removed and current directory
`/private/tmp/ace-market-p1d1-final-artifact.KpN1MF/probe`, outside both source checkouts. Exact
origins were:

- `ace`: `clean-venv/lib/python3.12/site-packages/ace/__init__.py`;
- `ace.application`: `clean-venv/lib/python3.12/site-packages/ace/application/__init__.py`;
- `ace.core`: `clean-venv/lib/python3.12/site-packages/ace/core/__init__.py`;
- `ace.intelligence`: `clean-venv/lib/python3.12/site-packages/ace/intelligence/__init__.py`.

Both installed `direct_url.json` records contained the exact source wheel URL and SHA-256. The
Market wheel has 95 members and 1,073,219 uncompressed bytes. The installed Market RECORD has 163
entries including installer-generated bytecode entries. Exactly 25 RECORD-owned Market JSON files
are installed, including all four P1D1 JSON artifacts. Every installed JSON byte equals both current
source and the corresponding wheel member, and every RECORD SHA-256 encoding was independently
verified. The wheel contains no adapter member or `domain_packs/tests`; the clean environment cannot
resolve `ace_market_public_product_source`. The existing single extension entry point remains
`b2b_marketing = ace_ext_b2b_marketing.marketing_extension:MarketingExtension`.

The P1D1 harness and conformance test have zero `core.engine` or `ace.core.engine` imports. The
clean-installed acceptance run reproduced the exact Brief, Pack, synthesis receipt, one provider
call, 18 negative results, and historical replay while loading Core and Pack resources only from
the clean venv.

The final artifact-bound command was:

```bash
cd /private/tmp/ace-market-p1d1-final-artifact.KpN1MF/probe
env -u PYTHONPATH \
  /private/tmp/ace-market-p1d1-final-artifact.KpN1MF/clean-venv/bin/python -I \
  /Users/eamirian/Projects/ace-ext-b2b-marketing/scripts/p1d1_prepared_brief_acceptance.py \
  --core-wheel /private/tmp/ace-p1d1-canonical-final.AujpoF/ace_core-0.3.0-py3-none-any.whl \
  --core-wheel-sha256 267cfed8ec3057439abf2a55e4f595e34c92f3b10f4e37c21a2e253a80b9dc4d \
  --market-wheel /private/tmp/ace-market-p1d1-canonical-final.8fBD9c/ace_ext_b2b_marketing-0.1.0-py3-none-any.whl \
  --market-wheel-sha256 895c2b0cbc975bfb264ebe8a48fe93280440019f8d6a993af81fa2de45f6134b
```

This command now fails closed if the running `ace` facade modules or any of the 25 Market JSON
resources resolve outside the corresponding supplied wheel's RECORD, even when unrelated files at
the supplied paths have the expected hashes. A control invocation from the source checkout with
the same correct wheel arguments failed before acceptance with
`ace-core direct-url archive digest does not match the supplied exact wheel`, proving that correct
files supplied as arguments cannot bless a different running installation.

## Verification record

- focused P1D1 conformance: 7 passed;
- formatted focused Market Pack/durable/P1D1 suite: 34 passed;
- all domain-pack tests with the separate adapter source explicitly present: 78 passed, 1 skipped;
- separately packaged adapter tests: 33 passed;
- all hermetic/non-provider Python tests across extension, domain packs, and adapter:
  549 passed, 12 skipped, 35 deselected;
- standalone P1D1 acceptance against the exact Core wheel: passed;
- clean installed-wheel P1D1 acceptance: passed;
- repository Ruff check: passed;
- P1D1 Ruff format check: passed;
- `git diff --check`: passed.

A literal unfiltered repository run completed with 579 passed, 12 skipped, and five failures that
are unrelated to P1D1: four provider-dependent paths failed because the Claude subprocess was
unavailable or returned fallback classification, and
`test_three_new_instruments_are_registered` exposed the already documented global instrument
registry provenance/order leak. The green hermetic gate disables extension autoload and deselects
`e2e`/`requires_extensions`; P1D1 itself performs no network or live provider call.

## Exact scoped file manifest

The worktree began intentionally dirty, with completed uncommitted P1A/P1B/P1C1/P1C2 work and
unrelated product changes. No unrelated baseline file was overwritten, staged, committed, pushed,
reset, stashed, or discarded. The P1D1 edit scope is exactly:

| Path | Action |
| --- | --- |
| `domain_packs/market_intelligence/releases/v0_4_0/manifest.json` | added inert 0.4.0 release manifest |
| `domain_packs/market_intelligence/releases/v0_4_0/modules/ontology.json` | added byte-identical release copy |
| `domain_packs/market_intelligence/releases/v0_4_0/modules/source_mapping.json` | added byte-identical release copy |
| `domain_packs/market_intelligence/releases/v0_4_0/modules/detection.json` | added byte-identical release copy |
| `domain_packs/market_intelligence/releases/v0_4_0/modules/synthesis.json` | added ordered v1alpha2 release copy |
| `domain_packs/market_intelligence/releases/v0_4_0/modules/personas.json` | added byte-identical release copy |
| `domain_packs/market_intelligence/releases/v0_4_0/conformance/p1d1_prepared_brief_input.json` | added exact input |
| `domain_packs/market_intelligence/releases/v0_4_0/conformance/p1d1_prepared_brief_expected.json` | added exact full public expected models |
| `domain_packs/market_intelligence/releases/v0_4_0/conformance/p1d1_prepared_brief_negative_cases.json` | added exact 18-case inventory |
| `domain_packs/market_intelligence/releases/v0_4_0/conformance/p1d1_prepared_brief_manifest.json` | added separate conformance manifest |
| `domain_packs/tests/test_market_intelligence_reasoned_brief_conformance.py` | added consumer conformance and frozen inventory guards |
| `scripts/p1d1_prepared_brief_acceptance.py` | added public-only acceptance harness |
| `docs/audits/ace-market-intelligence-p1d1-governed-routed-brief-2026-08-06.md` | added this evidence record |
| `domain_packs/tests/test_market_intelligence_durable_conformance.py` | refactored compatible helpers and restored `_batch` return |
| `domain_packs/tests/test_market_intelligence_pack.py` | added nested release package-data expectation |
| `README.md` | reconciled P1D1 release, proof, and limitations |
| `pyproject.toml` | pinned current Core artifact comment and nested package-data wildcards |
| `docs/ace-market-intelligence-extension-roadmap-2026-08-05.md` | reconciled P1D1 completion/current Core wheel and next gate |
| `docs/ace-market-intelligence-public-extension-pivot-2026-08-05.md` | reconciled P1D1 completion and scope |

`MANIFEST.in` was not changed; its existing recursive JSON rule already covers the nested release.
Every non-`releases/**` file under `domain_packs/market_intelligence` is guarded by an exact closed
inventory and SHA-256 map, preventing both byte mutation and unreviewed additions to the frozen
0.3.0 archive.

## Limitations and next dependency

This proof is deliberately narrow. Platform validates exact structure, declared support
attribution, temporal/activation binding, and atomic persistence. It does not determine semantic
entailment of arbitrary prose and this packet does not claim generalized hallucination detection.
The explicit fixture policy forbids invented competitor attribution, and the positive assertions
prove that policy for this one deterministic provider output.

The source material is PREPARED fixture data, not captured public evidence. Input source locators
describe extraction, while canonical final Brief citation locators remain null. The public
in-memory conformance store demonstrates the service contract and atomic semantics; production
database durability remains Platform evidence. The Core API is unreleased and therefore pinned to
the exact local wheel rather than declared as a published runtime dependency.

There is no LIVE Shift, Signal, or Brief, no source capture, delivery, Decision, Outcome, feedback,
UI, HTTP, MCP, or Content AI in P1D1. The next audited Market packet is P1E Decision/no-action →
Outcome → governed feedback. A separately governed LIVE Shift/Signal/routing bridge is required
before any LIVE Brief claim.
