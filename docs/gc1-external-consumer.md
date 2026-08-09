# Market Intelligence external governed-cognition journey

This repository is an independent consumer of ACE's governed-cognition product interface. The
two-phase verifier in [`scripts/gc1_external_consumer.py`](../scripts/gc1_external_consumer.py)
invokes only the public `ace` CLI. It never imports `ace` or `core.engine` Python modules, and it is
not included in the inert Domain Pack wheel.

The journey proves this sequence for one Market Intelligence reasoning pattern:

```text
accepted source task
  → non-selectable sourced proposal
  → semantic-diff inspection
  → explicit human approval
  → immutable active revision
  → materially attributed fresh use
  → ACE restart
  → byte-stable revision/head inspection
  → materially attributed use of the same revision
  → human-authorized retirement
  → subsequent use fails closed
```

## Prerequisites

- a running ACE deployment with the `ace cognition` command family;
- `ace login` completed for the target URL;
- a human operator token carrying `cognition-review` authority for approval and retirement; and
- one completed product-scoped task that contains the accepted reasoning worth teaching.

The command family is merged into ACE Core but is not yet available from a published post-0.4.1
artifact. Until that Core patch is tagged, published, and clean-installed, this verifier is
candidate evidence rather than a public GC1 pass.

## Prepare

Run from this repository, naming the existing source task and a new receipt path:

```bash
uv run python scripts/gc1_external_consumer.py prepare \
  --url http://localhost:8000 \
  --source-task task:SOURCE \
  --state-file /absolute/evidence/market-gc1-state-v1.json
```

Prepare refuses to replace an existing state file before issuing any command. It records proposal,
review, revision, active-head, selection, use, and material-use identities and hashes.

## Restart boundary

Stop and restart the ACE API and database using the deployment's supported procedure. Keep the
state file unchanged, then confirm health with `ace doctor`. A process restart without the durable
database is not the required test.

## Resume

```bash
uv run python scripts/gc1_external_consumer.py resume \
  --url http://localhost:8000 \
  --state-file /absolute/evidence/market-gc1-state-v1.json
```

Resume refuses a changed scenario, revision, or active head. It requires matching non-empty
selection/use revision sets, `used` state, and a material-use hash. After retirement it accepts only
a cognition-use failure code; connection errors and unrelated command failures cannot satisfy the
fail-closed gate.

## Evidence boundary

The completed state file is a local execution receipt. It does not establish publication,
cross-deployment behavior, beneficial reasoning quality, hostile-code isolation, distributed
approval, or autonomous learning. GC1 can advance only after the same journey is rerun from exact
public Core and Market artifacts and its public hashes and limitations are reconciled into Core's
roadmap evidence.
