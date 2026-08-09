# ACE Market Intelligence 0.6.0 — release-candidate record

**Status:** initial public repository and release candidate; not tagged or published
**Distribution:** `ace-domain-market-intelligence` 0.6.0
**Runtime requirement:** Python 3.12 and `ace-core>=0.4.1,<0.5`
**Artifact boundary:** 39 JSON resources; no Python, connector, entry point, or install hook

## What this candidate proves

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
| Isolated install | `ace-core==0.4.1`, Market `0.6.0` candidate wheel, World `0.8.0` |
| Installed-artifact dual compile | passed; distinct Pack IR digests |
| Installed-artifact dual activation and independent retirement | passed |
| Connector bundled or installed by root | no |

The historical negative-case harness uses its originally frozen Pydantic 2.12.5 development
environment. That pin is not published metadata and does not constrain an installing consumer.

## Remaining release steps

- merge the initial repository pull request;
- verify main-branch CI;
- record final tagged artifact digests;
- configure PyPI trusted publishing;
- tag `v0.6.0`, publish the GitHub Release, and verify a clean public-index installation; and
- reconcile the resulting two-domain evidence into ACE Core roadmap outcome GI2.

GI2 is not closed by this candidate. It closes only after the Market artifact is independently
published and the public two-domain journey is reproducible without a source checkout.

## Explicit limits

This candidate does not claim broad Market Intelligence coverage, production source connectors,
continuous monitoring, delivery, publishing, external action, autonomous promotion, or general
domain neutrality. The current compiled proof is the narrow competitor/product public-price path;
broader Market facets remain roadmap scope.
