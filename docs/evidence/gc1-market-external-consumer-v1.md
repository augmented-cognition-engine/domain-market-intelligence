# GC1 — Market external governed-cognition consumer (v1)

**Status:** external-consumer journey passed; Core reconciliation pending

**Date:** 2026-08-09

**Outcome:** GC1, supported governed-cognition builder journey

## Claim

An independent Market Intelligence consumer used only the public `ace` CLI from a clean
`ace-core==0.4.4` installation to teach, inspect, govern, materially use, restart, use again, and
retire one product-scoped reasoning revision. A distinct later request requiring the retired
cognition failed because no complete cognition-use attribution could be produced.

The verifier imports no `ace` or `core.engine` Python modules and is not included in the inert
Market Domain Pack wheel.

## Public identities

| Component | Public identity | Exact source |
|---|---|---|
| Core + Intelligence | `ace-core==0.4.4` | tag `v0.4.4`, commit `ca7ee1f1e04c02e43a2db05c3bb6355feb011180` |
| Market Domain Pack | `ace-domain-market-intelligence==0.6.0` | unchanged inert distribution |
| Consumer verifier | repository source outside the wheel | SHA-256 `ba0c63967514ae5b1966b1cac794f187ae2a0d29170fd75b23f4130f308e81d5` |
| Scenario | `ace.market.gc1-scenario/v1` | SHA-256 `b7dcdab1ac8bcb66cb46ed2a8ea90f1ccfc9f8307ef85b31fbe266d6faf166c3` |

The [0.4.4 GitHub Release](https://github.com/augmented-cognition-engine/core/releases/tag/v0.4.4)
is marked latest and resolves to the commit above. The
[trusted publication run](https://github.com/augmented-cognition-engine/core/actions/runs/31345474622)
completed successfully. PyPI published:

- `ace_core-0.4.4-py3-none-any.whl`, SHA-256
  `25949e984d68e1f917fc0aef9a123e550618d401ec4be73d2f49f21c77a9245e`;
- `ace_core-0.4.4.tar.gz`, SHA-256
  `85af82368f71abfa4da94a11b37049e760e42da7c30d4c0633a8f9a160b6eff9`.

A new Python 3.12 environment installed 0.4.4 from the refreshed public PyPI index. Distribution,
`ace.__version__`, `ace_mcp_client.__version__`, and Core runtime version all reported `0.4.4`;
`ace cognition --help` exposed the supported builder commands.

## Clean execution topology

- one public-package ACE API process;
- one SurrealDB process with a new logical namespace/database, migrated from schema v0 to v176;
- one authenticated product-scoped operator with `cognition-review` authority;
- one completed source task, `task:9295nllkmh074tv3pr58`;
- one state file carried across the API stop/start boundary; and
- no source checkout or locally built Core wheel on the runtime import path.

The API process was stopped after `prepare` completed. SurrealDB and its data remained running. A
new API process opened the same database at schema v176 before `resume` began.

## Durable receipt result

| Boundary | Exact result |
|---|---|
| Proposal | `cognition_proposal:a1306d345dfd5bc0e9fb7182905ab383`, initially non-selectable |
| Semantic diff | SHA-256 `5211778bfd65a2177894180029898fa80a27374246fb8819959261d46db342b5` |
| Human review | `cognition_review:2dead1ebed5de7e6fea92a553b6c3e5c`, disposition `approve` |
| Approved revision | `cognition_revision:02db82ccd8f2f5776bc49ef88f71ec62` |
| Active head | `cognition_head:dcc2299f646ad9a0a811f8bd4898a1c9`, generation 1 |
| Pre-restart material use | task `task:3ohtjhggviqo25arnoax`, material-use hash `919ac46758ee244fbf9e029b79155313d568aa08295e0c0e8097a7ca516872f5` |
| Post-restart material use | task `task:ino203d0bq12znb1dlmz`, same exact required revision and material-use hash |
| Retirement | `cognition_lifecycle:5d673126b4c5e84b46014c038b29fd74`, resulting head lifecycle `retired` |
| Distinct later request | rejected with `cognition_use_attribution_incomplete` |

The revision hash `e04977c31966cef53b85f64bbefa20b871f3223245463eab18f6700642d29730`
and active-head hash `7bb755abaabf53da8933de9981b4c377c79aab34f01087e7ad94a81cabf11f05`
were identical before and after restart. Both successful tasks had matching non-empty selection and
use revision sets that included the approved Market revision. The complete archived receipt is
[`gc1-market-external-consumer-v1.json`](gc1-market-external-consumer-v1.json), SHA-256
`b239b314b34c3dfedddb72907b63abe5bf3197013b8d1460466ff4942f714682`.

## Failure-control interpretation

ACE automatically replays an identical task request within its idempotency window. The verifier
therefore uses a separate `post_retirement_use_prompt` after retirement. This prevents an earlier
successful receipt from being mistaken for a new eligibility decision. A hermetic regression test
requires the restart and post-retirement prompts to differ.

The public CLI also emits a progress line before the final JSON task receipt. The consumer parser
accepts that documented shape while still requiring exactly one trailing JSON object; non-receipt
output fails closed.

## Verification

- external verifier contract suite: 7 passed;
- Ruff check: passed;
- public Core 0.4.4 release gates: 7,378 normal and 7,376 extension-disabled tests passed;
- all six official Core pull-request checks: passed;
- trusted PyPI publication: passed; and
- clean prepare/restart/resume execution: passed.

## Limitations

This proves the supported lifecycle and durability on ACE's documented single-node topology. It
does not prove reasoning quality, cross-database portability, distributed approval, hostile-code
isolation, general causal accuracy, autonomous learning, or beneficial real-world outcomes. The
Market revision was selected alongside Core-default cognition; the receipt proves inclusion and
material use of the exact approved revision, not exclusive use of that revision.

## Reconciliation decision

The Market external-consumer gate is passed. ACE Core must separately archive this public record,
reconcile its GC1 outcome row, and decide whether any unimplemented `measure`, `revise`, rollback,
or supersession promise remains part of the same outcome before changing GC1 to `passed`.
