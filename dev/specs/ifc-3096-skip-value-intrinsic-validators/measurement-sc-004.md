---
description: "SC-004 measurement record — proxy timing of the constraint-validation stage, not a full-stack rebase"
---

# SC-004 measurement record

**This is a PROXY measurement, not the wall-clock of a real data-only rebase.** Read
[what it does not measure](#what-this-does-not-measure) before quoting any number from it.

## Why a proxy

SC-004 asks for before-and-after wall-clock for a data-only rebase against a populated dev stack.
The measurement environment had only the supporting containers running (Neo4j, Redis, RabbitMQ,
Prefect and its Postgres) — no `infrahub-server` and no task worker. Producing a real figure would
have required standing up the full stack twice, once per code state, against a rebuilt image. That
was out of budget for the session, so the number below was produced instead, and is labelled as a
proxy everywhere it appears.

Nothing here is estimated or extrapolated. Both sides were measured, on the same process, against
the same real Neo4j.

## What was measured

The stage of a data-only branch operation that this change actually touches: constraint
determination followed by execution of the scheduled checkers against a populated database.

Per timed round:

1. `build_constraint_validator_determiner(...).get_constraints(schema_branch, node_diffs)` — the
   data-diff producer, over a data-only node diff.
2. For every constraint it returned, `AggregatedConstraintChecker.run_constraints(...)` built from
   `AggregatedSchemaConstraintsDependency` — the same aggregation the schema-path validation task
   uses, so the checkers' Cypher runs against the real population.

**Before** and **after** are the same process. The "before" side sets
`triggered_by_data_change = True` back on the eight flipped checker classes for the duration of the
round, which reproduces the pre-change scheduling exactly. One warm-up round is discarded in each
mode, then the two modes are interleaved round by round so query-plan caching cannot land on one
side.

Script: [`benchmarks/sc004_proxy_benchmark.py`](./benchmarks/sc004_proxy_benchmark.py).

Environment: local Neo4j `infrahub-database-1` (`neo4j:2026.05.0-enterprise`), Python 3.14.3,
`INFRAHUB_USE_TEST_CONTAINERS=false`, WSL2. Measured 2026-08-31.

Schema: the `car_person_schema` fixture. Data-only diff touching six attribute pairs
(`TestCar.name`, `nbr_seats`, `color`, `is_electric`, `transmission`; `TestPerson.height`), one
relationship pair (`TestCar.driver`), and three set value-intrinsic parameters (`color` contributes
both `max_length` and its mirrored `parameters.max_length`; `transmission` contributes `enum`).

## Results

| Population | Scheduled constraints (before → after) | Before, median of 5 | After, median of 5 | Reduction |
|---|---|---|---|---|
| 550 nodes (500 `TestCar` + 50 `TestPerson`) | 27 → 11 | 0.2877 s | 0.0795 s | **72.4 %** |
| 2200 nodes (2000 `TestCar` + 200 `TestPerson`) | 27 → 11 | 1.0637 s | 0.3099 s | **70.9 %** |

Raw per-round times, 2200 nodes:

- before: `[1.0637, 0.9367, 1.0964, 0.9941, 1.1021]` s
- after: `[0.3099, 0.2795, 0.3855, 0.2835, 0.3224]` s

Raw per-round times, 550 nodes:

- before: `[0.2877, 0.3047, 0.2708, 0.3267, 0.2677]` s
- after: `[0.0794, 0.0794, 0.0812, 0.0795, 0.0975]` s

The constraint drop of 16 (27 → 11) is exactly `2A + R + P` for this diff — `A = 6`, `R = 1`,
`P = 3` — which is the SC-002 formula the parametrized determiner test pins.

The reduction is roughly constant across the two population sizes because the removed work is
whole-population scans: both sides grow with the population, so the ratio holds while the absolute
saving grows.

## What this does not measure

- **A real rebase.** No `infrahub-server`, no task worker, no Prefect flow, no HTTP or message-bus
  round trips, no diff computation, no merge writes. The saving here is a saving on *one stage* of a
  rebase; what fraction of an end-to-end rebase that stage represents is **unmeasured**.
- **Prefect task overhead per constraint.** In production each constraint becomes its own Prefect
  task in a batch. Removing 16 constraints removes 16 task submissions too, which this proxy does
  not count — so it under-reports the production saving on that axis.
- **A production-shaped schema and population.** Two kinds, seven fields, uniform data. A real
  deployment has many more kinds, so the number of `(kind, field)` pairs in a data diff — and hence
  the constraint count on both sides — differs.
- **Concurrency.** Rounds run serially against an otherwise idle database.

## What still needs measuring before the SC-004 claim can be made

A real before/after wall-clock of `infrahub branch rebase` (or the rebase flow triggered through the
API) on a dev stack loaded with a known dataset, run once with the branch at its pre-change commit
and once at `HEAD`, recording the node population. Until that exists, quote the figures above as
"constraint-validation stage, proxy measurement", never as "rebase is 70 % faster".
