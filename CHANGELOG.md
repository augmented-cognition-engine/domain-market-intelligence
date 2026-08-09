# Changelog

All notable changes to `ace-domain-market-intelligence` are recorded here. The project follows
Semantic Versioning.

## Unreleased

### Added

- Two-phase external GC1 consumer verifier over the public `ace cognition` CLI, covering sourced
  proposal, semantic diff, human approval, exact material use, restart, exact later use,
  retirement, and fail-closed subsequent selection without importing Core internals.

### Documentation

- Reconcile the 0.6.0 GitHub/PyPI publication and GI2 closeout status.

## [0.6.0] — 2026-08-09

Initial public Domain Pack distribution extracted from the legacy executable B2B Marketing
extension.

### Added

- JSON-only Market Intelligence ontology, source mapping, numeric detection, personas, synthesis,
  and bounded decision/outcome policy.
- Frozen conformance history for Market P1A through P1F.
- Separate, optional public-product source connector boundary with an injected transport and no
  bundled network client.
- Release-contract and cross-domain GI2 gates against `ace-core` 0.4.1 and World Intelligence 0.8.0.
- Historical harness imports migrated to the public `ace.intelligence.packs` namespace shipped by
  ACE Core 0.4.1; the P1E harness digest was re-pinned without changing its pack, input, expected,
  or negative-case payloads.

### Boundary

The root distribution contains no executable code, connector, application UI, credentials, entry
points, or install hooks. Publication of the connector is not part of this release.
