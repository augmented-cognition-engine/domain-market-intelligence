# Contributing to ACE Market Intelligence

Market Intelligence is an independently versioned consumer of ACE Core + Intelligence.
Contributions must preserve the boundary that makes the domain reusable: Domain Packs are inert
declarative data; connectors are separate reviewed executable packages; Core owns authority,
persistence, reasoning, and durable receipts.

Before starting, read the [README](README.md), [roadmap](ROADMAP.md), and
[security policy](SECURITY.md). Open an issue before changing a public ontology, detector, synthesis,
feedback, or connector contract so identity and compatibility consequences are visible.

## Development

Use Python 3.12 and `uv`:

```bash
uv sync --frozen --no-install-project
uv run --no-sync pytest
uv run --no-sync pytest tests/test_release_contract.py
uv run --no-sync ruff check --no-cache tests scripts/gc1_external_consumer.py
uv run --no-sync ruff format --check --no-cache tests scripts/gc1_external_consumer.py
```

Add or update conformance fixtures for semantic changes. Never put credentials, network access,
imperative control flow, or action authority in a Domain Pack. Do not widen the `ace-core`
compatibility window without proving the complete locked and installed-artifact gates.

By contributing, you agree that your contribution is licensed under Apache-2.0 and that project
interactions follow the [Code of Conduct](CODE_OF_CONDUCT.md).
