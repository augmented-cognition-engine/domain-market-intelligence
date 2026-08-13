# ACE Market Intelligence 0.7.0 — release candidate

Status: **candidate — Market review, CI, and public-index gates pending**

## Promise

Market 0.7.0 is the installable Market Intelligence experience for ACE's generic Intelligence
Catalog. It lets a team begin with the intelligence outcome it needs, choose reviewed evidence
groups, and continue through the existing governed Builder without turning the Domain Pack into
application code or downstream content production.

## Coordinates

- source base: Market main merge `9e022fceafdee166aafcef3ad15ddd1d2f79eaf4`;
- release branch: `codex/v0.7.0-intelligence-os-release`;
- candidate root distribution: `ace-domain-market-intelligence==0.7.0`;
- required Core line: `ace-core>=0.8.2,<0.9`;
- exact public Core release: [`v0.8.2`](https://github.com/augmented-cognition-engine/core/releases/tag/v0.8.2), clean-installed from PyPI;
- paired domain validation: World Intelligence 0.12.0;
- exact public World release: [`v0.12.0`](https://github.com/augmented-cognition-engine/domain-world-intelligence/releases/tag/v0.12.0), published through trusted PyPI;
- source-available connector candidate: 0.2.0, separately packaged and non-transitive.

## Included change

- six outcomes: competitive, product, market, customer, performance, and narrative/messaging
  intelligence;
- five evidence groups: competitor public evidence, company/market records, news/social,
  customer voice, and owned marketing/revenue systems;
- private/owned evidence is opt-in;
- every selection remains declarative and non-authorizing;
- the root wheel remains JSON-only with no Python, connector, entry point, or install hook.

## Acceptance before publication

- Core 0.8.2 and World 0.12.0 exist on public indexes;
- the frozen Market lock has no Core/World Git or path override;
- the complete conformance, adapter, release-contract, wheel, and GI2 regression gates pass;
- an isolated two-domain install admits both profiles through the unchanged Core resource plane;
- historical 0.6.0 pack bytes and GI2 evidence remain frozen and exact.

## Candidate verification

- the frozen lock resolves public `ace-core==0.8.2` and
  `ace-domain-world-intelligence==0.12.0` with no Git or path override for either;
- the complete isolated Python 3.12 suite passes with `136 passed, 1 skipped`;
- root and separately packaged connector candidates build and pass focused contract validation;
- a checkout-free Python 3.12 environment installs the Market candidate wheel with public Core
  0.8.2 and World 0.12.0, resolves both profiles, and confirms the connector is absent;
- final CI, immutable hashes, and the public Market install remain publication closeout gates.

## Boundaries

This candidate does not create content, run campaigns, publish, execute effects, grant source
access, or claim the full planned Market ontology is implemented. Connectors remain separately
reviewed host software; HPE-specific configuration remains private deployment policy rather than
public pack content.
