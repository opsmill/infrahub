# Feature Specification: Profile merge and rebase recompute cost at scale

**Feature Branch**: `merge-recompute-profile-ifc-2761`
**Created**: 2026-06-22
**Status**: Draft
**Jira**: [IFC-2761](https://opsmill.atlassian.net/browse/IFC-2761) (epic [IFC-2705](https://opsmill.atlassian.net/browse/IFC-2705)) — first task only
**Input**: Profile branch merge and rebase recompute cost at scale to locate the dominant cost center before any coalescing redesign.

## Overview

Branch merge and rebase recompute derived values (computed attributes, display labels, HFIDs) by emitting one node event per changed node in the data diff; each event is matched against the per-node automations and submits a recompute job. On large branches this fan-out is the suspected dominant cost behind the reported degraded-instance window (about 20 minutes unusable) and very long merges (about 1 hour at scale), but the magnitude and the breakdown across cost centers have never been measured.

This feature delivers a reproducible profiling harness and a findings report that attribute the recompute cost of a merge or rebase at increasing scale. The goal is a confident, evidence-based answer to "where does the cost actually go," so the coalescing redesign (a separate follow-up effort) targets the real bottleneck instead of an assumed one. This work measures only; it does not change recompute behavior.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Attribute merge recompute cost across cost centers (Priority: P1)

An engineer needs to know how a merge's time and work split across the candidate cost centers (the per-node event fan-out and automation matching, the recompute job executions, schema migrations, the database commit) so the redesign targets the largest one.

**Why this priority**: Without an attribution, the redesign would be guesswork. The whole epic's design decision depends on knowing which cost center dominates.

**Independent Test**: Run a merge over a synthetic dataset of a known size and obtain a report that breaks the merge's wall-clock and work counts down by cost center.

**Acceptance Scenarios**:

1. **Given** a synthetic branch with a known number of changed nodes across kinds carrying computed attributes, display labels, and HFIDs, **When** the branch is merged through the harness, **Then** the report states the number of node events emitted, the executed recompute runs, and the wall-clock attributed to each cost center.
2. **Given** the same merge, **When** the report is produced, **Then** it names the single dominant cost center for that run.

---

### User Story 2 - Characterize how cost grows with changed-node count (Priority: P1)

An engineer needs to know whether recompute work grows linearly or super-linearly with the number of changed nodes, because that determines whether coalescing the fan-out is the right lever and how urgent it is.

**Why this priority**: A linear cost dominated by sheer volume implies a different fix than a super-linear cost. The growth curve is the core finding that justifies (or redirects) the redesign.

**Independent Test**: Run the merge at three or more scales and confirm the report shows each metric per scale and classifies the growth.

**Acceptance Scenarios**:

1. **Given** runs at small, medium, and large changed-node counts (for example about 10, 100, and 1000+), **When** the results are compared, **Then** the report shows how node events, executed recompute runs, and per-cost-center time scale with the changed-node count.
2. **Given** those results, **When** the growth is classified, **Then** the report states whether each metric is linear or super-linear in the changed-node count.

---

### User Story 3 - Reproducible, retained harness (Priority: P2)

An engineer needs to re-run the profile later — to confirm a number, and to re-measure after the coalescing redesign lands — so the harness must be a retained, repeatable artifact rather than a throwaway.

**Why this priority**: The same harness is the before/after yardstick for the redesign and a guard against future regression. A one-off measurement can't serve that.

**Independent Test**: Re-run the harness and confirm it reproduces the metrics within run-to-run variance, without manual setup beyond a documented entry point.

**Acceptance Scenarios**:

1. **Given** the committed harness, **When** it is run a second time at the same scale, **Then** it reproduces the same metrics within a stated tolerance.
2. **Given** the harness, **When** a future change alters recompute behavior, **Then** the harness can be re-run to compare against the recorded baseline.

---

### Edge Cases

- **Merge with schema changes vs pure data merge**: schema migrations run on merge only when the branch changed the schema; the report must separate migration cost from the per-node fan-out so a data-only merge and a schema-changing merge are distinguishable.
- **Merge vs rebase**: both paths emit the per-node fan-out; the harness must cover both, or explicitly record which path a given run measured.
- **Relevance mix**: a branch may change many nodes of which few feed any derived value; the dataset should let the changed-node count and the derived-value count vary independently so the report does not conflate them.
- **Asynchronous recompute**: recompute jobs run in the background after the merge transaction; the report must be clear about which cost is inside the merge critical path versus the trailing recompute work that produces the degraded-instance window.
- **Run-to-run variance**: timing on a containerized stack varies; the report must state the tolerance and avoid drawing conclusions inside the noise.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The harness MUST drive a real branch merge and a real branch rebase over a synthetic dataset whose size (changed-node count) is configurable.
- **FR-002**: The synthetic dataset MUST include kinds that carry computed attributes, display labels, and HFIDs, so all three derived-value families are exercised.
- **FR-003**: The harness MUST record the number of node events **emitted** by the merge or rebase, by event type. This emitted-event cardinality is the fan-out driver and is the counting layer's primary signal.
- **FR-004**: The harness MUST record how much recompute the emitted events cause, observed as **executed** recompute runs on the real stack (the timing layer). Recompute is dispatched by the event-to-automation engine, not issued synchronously by the merge flow, so it is not captured by intercepting the merge's own workflow calls. The counting layer MAY additionally record a **derived expected-recompute** count by applying the same dependency/automation match logic in-process.
- **FR-005**: The harness MUST attribute the merge or rebase wall-clock across, at minimum: the per-node event fan-out and automation matching, the executed recompute runs, and schema migrations. It SHOULD additionally attribute the database commit / merge internals where finer attribution is available (best-effort).
- **FR-006**: The harness MUST run at three or more scales and report every metric per scale.
- **FR-007**: The findings MUST identify the dominant cost center and classify how each metric grows with the changed-node count (linear vs super-linear).
- **FR-008**: The findings MUST distinguish cost inside the merge critical path from trailing asynchronous recompute work.
- **FR-009**: The harness and its findings MUST be retained as committed artifacts and runnable from a documented entry point.
- **FR-010**: The work MUST NOT change recompute behavior or produced derived values; the instance MUST behave identically whether or not the harness is present.

### Key Entities *(include if feature involves data)*

- **Synthetic dataset**: A schema plus seeded nodes designed for the profile — kinds with computed attributes, display labels, and HFIDs, and a configurable count of changed nodes on a branch to be merged or rebased.
- **Cost center**: A distinct contributor to merge or rebase time (per-node event fan-out and matching, recompute execution, schema migration, database commit) that the report measures separately.
- **Profile run**: One execution of a merge or rebase at a given scale, producing the recorded metrics.
- **Findings report**: The retained summary that aggregates runs across scales, states the dominant cost center, and classifies growth.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A single documented run produces, at each chosen scale, full cost attribution for a merge plus emitted-event and executed-recompute cardinality for both merge and rebase. Rebase wall-clock attribution is a follow-up (see Assumptions).
- **SC-002**: The report shows the growth of recompute work against the changed-node count across at least three scales and classifies it as linear or super-linear.
- **SC-003**: The report names the dominant cost center with evidence sufficient for the team to choose the coalescing design (or to redirect if the dominant cost is elsewhere).
- **SC-004**: A second run at the same scale reproduces the metrics within a stated tolerance.
- **SC-005**: Derived values and recompute behavior are unchanged by this work, confirmed by existing recompute tests continuing to pass.

## Assumptions

- The cost mechanism (one node event per changed node, matched against the per-node automations, each match submitting a recompute job) is established from the merge and rebase code; this work measures its magnitude, not its existence.
- Merge and rebase do not emit a schema-update event, so the schema-update backfill path is out of scope here (closed under IFC-2759); the relevant recompute on this path is the per-node data-driven fan-out.
- Representative scale can be reproduced with synthetic data on the existing containerized test stack; absolute numbers will differ from production hardware, but growth shape and relative cost attribution are expected to transfer.
- The coalescing redesign is explicitly out of scope and gated on these findings; this spec covers measurement only.
- The merge/rebase correctness gap for nodes absent from the source branch (IFC-2758) and the transform-on-git-import axis (IFC-2760) are out of scope; coordination with IFC-2758 is noted because both touch the merge path.
- Existing test infrastructure and schema fixtures are reused where they fit, rather than building a parallel harness.
- The timing (wall-clock) layer focuses on merge, the epic's headline path. Rebase shares the same per-node mechanism and is covered for emitted-event and recompute cardinality in the counting layer; rebase wall-clock attribution is deferred unless the merge timing proves insufficient to choose the redesign.
- Terminology: **emitted events** are counted in the counting layer (no worker); **executed recompute runs** are observed in the timing layer via the workflow engine's run records; a **derived expected-recompute** count is an optional in-process prediction. Recompute is dispatched by the event-to-automation engine, not issued synchronously by the merge, so the counting layer does not observe recompute submissions directly.
