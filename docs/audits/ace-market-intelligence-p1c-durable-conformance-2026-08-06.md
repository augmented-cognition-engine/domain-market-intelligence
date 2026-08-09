# Market P1C — durable prepared price-move conformance evidence

**Date:** 2026-08-06
**Scope:** Historical Platform P1B durable consumer proof; this does not complete Platform P1.
**Current evidence:** [Market P1C1 public source-mapping consumer evidence](ace-market-intelligence-p1c1-public-source-mapping-2026-08-06.md)

## Dependency gate

The exact Platform P1B wheel was verified before implementation:

```text
shasum -a 256 /tmp/ace-p1b-final-wheel.nzRDvs/dist/ace_core-0.3.0-py3-none-any.whl
1af7e57091544534f4bd40b5e469d040d0f77090bdce0c0abc60749158eff5ff
```

An isolated wheel install successfully imported
`PreparedIntelligenceLedgerService`, `PreparedResourceAdmissionV1Alpha1`, the attention and
immutable-record contracts, `InMemoryImmutableRecordStore`, and
`exercise_prepared_ledger_restart` through public `ace.application`, `ace.intelligence`,
`ace.core`, and `ace.testing` modules. The imported `ace` package resolved from that isolated
wheel installation, not `/Users/eamirian/Projects/ace-core`.

## Focused conformance

```text
PYTHONPATH=/tmp/ace-market-p1c-gate.venv/lib/python3.12/site-packages \
  /Users/eamirian/Projects/ace-core/.venv/bin/python -m pytest \
  domain_packs/tests/test_market_intelligence_pack.py \
  domain_packs/tests/test_market_intelligence_durable_conformance.py \
  -q --tb=short
27 passed in 0.32s
```

The 27 tests comprise the existing 15 Domain Pack tests and 12 durable consumer cases. They prove
the exact existing Shift, Signal, and Brief identities; the full seven-resource admission plus
attention receipt; exact replay and fresh-service reopen; historical isolation; all eight declared
negative vectors; atomic interruption; cross-product fencing; foreign activation and Pack
rejection; divergent replay rejection; lineage mismatch rejection; and PREPARED/LIVE separation.

## Static, format, JSON, and boundary gates

```text
/Users/eamirian/Projects/ace-core/.venv/bin/ruff check \
  ace_ext_b2b_marketing domain_packs/tests
All checks passed!

/Users/eamirian/Projects/ace-core/.venv/bin/ruff format --check \
  domain_packs/tests/test_market_intelligence_pack.py \
  domain_packs/tests/test_market_intelligence_durable_conformance.py
2 files already formatted
```

All 10 packaged Market JSON files parse, and all four conformance-manifest digests match their
exact bytes. `git diff --check` passes. An AST import scan of both Domain Pack consumer test files
found only public `ace.application`, `ace.application.domain_activation`, `ace.core`,
`ace.intelligence`, and `ace.testing` imports and no `core`, `core.engine`, or private `ace._*`
imports. The packaged Domain Pack remains JSON-only.

The repository-wide formatting check is not green: it reports 122 pre-existing extension and test
files that would be reformatted. Those unrelated dirty files were preserved; only the two focused
P1 test files were checked and are formatted. Repository-wide Ruff lint is green.

## Broader Market suite

```text
PYTHONPATH=/tmp/ace-market-p1c-gate.venv/lib/python3.12/site-packages \
  /Users/eamirian/Projects/ace-core/.venv/bin/python -m pytest \
  ace_ext_b2b_marketing/tests domain_packs/tests \
  -m "not e2e and not requires_extensions" -q --tb=short
1 failed, 464 passed, 11 skipped, 35 deselected in 2.62s
```

The one failure is the unrelated, order-dependent legacy
`test_three_new_instruments_are_registered`: running
`test_instrument_registry.py` first leaves global instrument provenance that conflicts with the
later registration. The failing test passes alone (`1 passed in 0.47s`), and the two-file order
reproduces the issue (`1 failed, 6 passed in 0.62s`). Preserving unrelated lifecycle code, the
broader suite excluding only that known test passes:

```text
464 passed, 11 skipped, 36 deselected in 2.22s
```

## Wheel and clean-install proof

The Market wheel was built with:

```text
/Users/eamirian/Projects/ace-core/.venv/bin/python -m build \
  --wheel --no-isolation --outdir /tmp/ace-market-p1c-dist .
```

Result:

```text
/tmp/ace-market-p1c-dist/ace_ext_b2b_marketing-0.1.0-py3-none-any.whl
sha256:94808b31e626b844c6d4f5dc3979479eb3193757ccd4ec8b1dc455a063ca823e
```

Wheel inspection found all 10 Pack and conformance artifacts, including
`p1c_durable_price_move_expected.json`; its installed bytes retain digest
`sha256:76b15c31edafd20bf4515f89a24ea52e0fb04d3b6ab63b8435a398891ef579b7`.
The wheel contains no tests, `__pycache__`, `.pyc`, `.pyo`, or build paths.

The clean environment was created at `/tmp/ace-market-p1c-clean.venv`. Core and Market were
installed together from the two exact local wheel paths with `--no-deps`; only generic
`pydantic`, `pytest`, and `pytest-asyncio` test dependencies were installed afterward. Installed
distribution metadata records these exact origins:

```text
UV_CACHE_DIR=/tmp/ace-market-p1c-clean-uv-cache \
  uv venv /tmp/ace-market-p1c-clean.venv
UV_CACHE_DIR=/tmp/ace-market-p1c-clean-uv-cache \
  uv pip install --python /tmp/ace-market-p1c-clean.venv/bin/python --no-deps \
  /tmp/ace-p1b-final-wheel.nzRDvs/dist/ace_core-0.3.0-py3-none-any.whl \
  /tmp/ace-market-p1c-dist/ace_ext_b2b_marketing-0.1.0-py3-none-any.whl
UV_CACHE_DIR=/tmp/ace-market-p1c-clean-uv-cache \
  uv pip install --python /tmp/ace-market-p1c-clean.venv/bin/python \
  pydantic pytest pytest-asyncio
```

```text
ace-core 0.3.0 -> file:///tmp/ace-p1b-final-wheel.nzRDvs/dist/ace_core-0.3.0-py3-none-any.whl
ace-ext-b2b-marketing 0.1.0 -> file:///tmp/ace-market-p1c-dist/ace_ext_b2b_marketing-0.1.0-py3-none-any.whl
```

The Core wheel SHA-256 was recomputed inside the clean verification flow and matched the required
digest. The installed `ace` import resolved under the clean environment's `site-packages`, all
required public seams imported, and the clean interpreter ran the focused repository-owned
conformance harness successfully:

```text
/tmp/ace-market-p1c-clean.venv/bin/python -m pytest \
  domain_packs/tests/test_market_intelligence_pack.py \
  domain_packs/tests/test_market_intelligence_durable_conformance.py \
  -q --tb=short
27 passed in 0.27s
```

Running the same source test paths from `/tmp` initially produced one collection error because the
wheel correctly excludes `domain_packs.tests` and the durable test reuses that repository-owned
fixture helper. Running from the worktree with the same clean interpreter supplies only the test
harness; Core and Market remain installed from the exact wheels, while separate wheel inspection
proves the installed Pack bytes. No package resolver was permitted to select another Core wheel.

## Honest boundary

This evidence proves the Market pack against Platform's public durable PREPARED conformance seam.
Every admitted resource and receipt remains PREPARED; commitment is non-live; the attention route
has no delivery authority. Production SurrealDB durability is separately owned and proved by ACE
Platform and is not reimplemented or independently claimed here. Live authority, source mapping,
executable capture, acquisition-receipt resolution, Core Brief reasoning and template enforcement,
Decision/no-action, Outcome, delivery, and learning remain open.
