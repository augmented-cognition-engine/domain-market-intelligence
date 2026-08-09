# ACE Market Intelligence 0.6.0 — release record

**Status:** public GitHub Release and PyPI package
**Distribution:** `ace-domain-market-intelligence` 0.6.0
**Runtime requirement:** Python 3.12 and `ace-core>=0.4.1,<0.5`
**Artifact boundary:** 39 JSON resources; no Python, connector, entry point, or install hook

## What this release proves

1. The frozen Market P1A–P1F conformance history is preserved in a repository that contains no
   legacy application UI or private Intelligence runtime.
2. The root distribution is inert and the public-product connector remains a separately reviewed,
   optional artifact.
3. Market and World compile through the same public `ace-core==0.4.1` pack compiler.
4. Both domains bind active revisions under one product without pack, entity, activation, persona,
   authority, or policy identity collision.
5. Retiring Market appends only to Market's activation history; World remains actively and exactly
   bound.

## Verification

| Gate | Result |
|---|---|
| Complete pack, connector, release-contract, and GI2 suite | **126 passed, 1 skipped** |
| Root release-contract suite | passed |
| Ruff focused release checks | passed |
| Actionlint | passed |
| Twine strict metadata validation | passed |
| Wheel boundary | **39 JSON resources, zero executable code files** |
| Isolated install | public `ace-core==0.4.1`, Market `0.6.0`, and World `0.8.0` packages |
| Installed-artifact dual compile | passed; distinct Pack IR digests |
| Installed-artifact dual activation and independent retirement | passed |
| Connector bundled or installed by root | no |

The historical negative-case harness uses its originally frozen Pydantic 2.12.5 development
environment. That pin is not published metadata and does not constrain an installing consumer.

## Publication

- [GitHub Release v0.6.0](https://github.com/augmented-cognition-engine/domain-market-intelligence/releases/tag/v0.6.0)
- [PyPI package](https://pypi.org/project/ace-domain-market-intelligence/0.6.0/)
- [Trusted-publication workflow](https://github.com/augmented-cognition-engine/domain-market-intelligence/actions/runs/31333497948)
- Wheel SHA-256: `73220bbd16d295734e7dc322147e6e3137752306ef9758f48fa6aecabdfeb080`
- Source-distribution SHA-256: `8082a5589f9608fa9d7f9827a8986d5413514d57e5878bcba7e829fb47388575`

The public two-domain install, activation, and independent-retirement journey passed and is bound
into Core's
[GI2 public cross-domain evidence](https://github.com/augmented-cognition-engine/core/blob/main/docs/evidence/gi2-public-cross-domain-falsification-v1.md).

## Explicit limits

This release does not claim broad Market Intelligence coverage, production source connectors,
continuous monitoring, delivery, publishing, external action, autonomous promotion, or general
domain neutrality. The current compiled proof is the narrow competitor/product public-price path;
broader Market facets remain roadmap scope.
