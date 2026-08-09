# ACE Market Intelligence P1F governed LIVE bridge audit

**Date:** 2026-08-06
**Result:** passed for the bounded LIVE Observation → Entity Snapshot → Shift → Signal → route → Brief slice
**Not claimed:** scheduling, delivery, external action, Decision/Outcome capture, or LIVE learning

## Outcome

P1F joins the previously separate LIVE-source and governed-reasoning proofs through public ACE
Core + Intelligence contracts. The Market repository remains the consumer: its JSON Domain Pack
provides the detector, routing, persona, and Brief vocabulary, while the source adapter remains a
separate executable package.

Two governed public-product observations establish a USD 1,200 baseline and a USD 1,080 current
state. ACE detects the 10% price decrease, admits a LIVE Shift and Signal, selects the configured
competitive route, and synthesizes a cited `Competitive Price Move Brief`. Core authorization
receipts govern both immutable appends. No delivery authority or external action is introduced.

## Exact result

- Shift: `shift:24095ad9e5f627c19e790b8aee71dd8c`
- Signal: `signal:5cefff328ba9131f33aec66e57953fe2`
- Route: `route_competitive_price_move`
- Template: `competitive_price_move_brief`
- Brief: `brief:f394e4711d8134fffde7bf0ee9bf9912`
- Brief evidence: two citations and four grounded claims
- First synthesis provider calls: `1`
- Fresh-service replay provider calls: `0`
- Delivery authority: `false`
- External actions: none

The fresh-service proof reconstructs both application services and the governed reasoning service
over the existing immutable state. Its provider deliberately raises if invoked; derivation and
Brief replay still return the exact canonical records.

## Negative boundary

The packet rejects four fail-closed cases:

1. divergent derivation replay;
2. divergent Brief replay;
3. PREPARED-mode promotion into the LIVE Brief service; and
4. a source snapshot coordinate that is not bound to its admitted immutable envelope.

No failed case leaves a newly admitted Shift, Signal, route, Brief, or external-action effect.

## Verification

| Check | Result |
|---|---:|
| Complete ACE Intelligence suite | 255 passed |
| Focused ACE legacy compatibility suites | 77 passed |
| Complete Market Domain Pack suite | 88 passed, 1 expected skip |
| Market P1F conformance suite | 4 passed |
| Core and Market lint gates | passed |
| Isolated installed-wheel consumer | passed |

Artifact pins:

- Core `ace_core-0.3.0-py3-none-any.whl`:
  `49214a347ce4d4e9d8aa65aca430f3278b2d8079dfaa7c9cba9edfc7fdfeabb5`
- Market `ace_ext_b2b_marketing-0.1.0-py3-none-any.whl`:
  `3ea4af28dce17207ff9151d4e5b346033b4561f2595ca6374db64137c6ed786a`
- Source adapter `ace_market_public_product_source-0.1.1-py3-none-any.whl`:
  `0285f7e50f2e40eef43bf2c24fff7f46acdcdaa6f21853ef1744ac3585a9f983`
- Installed probe environment: `/private/tmp/ace-p1f-probe-final`

The probe ran from `/private/tmp`, loaded ACE, the Market 0.6.0 conformance packet, and the public
source adapter from their installed wheels, and reproduced the exact positive projection. The
0.6.0 directory is a conformance release packet over unchanged Market Domain Pack `0.3.0`; it is
not a hidden pack-schema or runtime fork.

## Roadmap reconciliation

P1F closes Platform P1's first end-to-end LIVE intelligence path. The next active packet is World
P2A: World Intelligence must compile through the same Pack schema using materially different event,
claim, provenance-family, contradiction, correction, uncertainty, and semantic-shift meaning. Any
World or political branch in the platform fails that falsification test. Corporate Strategy
Intelligence follows as the third-domain proof.
