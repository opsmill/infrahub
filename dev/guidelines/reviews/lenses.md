# Structural lenses

> Part of: `dev/guidelines/reviews/` | Related: [Structural Review](README.md), [Reporting](reporting.md)

Four lenses, each with the signals that make a crossing worth looking at and the question that turns
it into a finding. A threshold that is crossed is a candidate, nothing more.

## Lens A: N+1, solving the instance instead of the class

| Signal | Threshold |
| --- | --- |
| New or grown hardcoded kind set `{InfrahubKind.X, …}` | any |
| Dispatch branches on one discriminant (`kind`, `inherit_from`, `isinstance`) in one function | ≥ 3, or an existing ≥ 3 grows |
| `bool` mode flag added to signatures in one file | ≥ 2 |
| Extra pass or phase added to a sequence, hardcoded ordering | reading only |

Ask: what concrete event is N+1? What design absorbs that event with no new code? Count the sites
that have to change when it arrives: sets, flagged signatures, call sites, tests pinning the order.
Three or more sites is a high cost of deferring.

## Lens B: Size and responsibilities

| Signal | Threshold |
| --- | --- |
| File crosses size | base < 500 LOC ≤ head |
| Large file keeps growing | base ≥ 1 000 and diff ≥ +50 LOC |
| Package crosses size | head ≥ 30 files or ≥ 3 000 LOC, base below |

Ask: is the growth a new responsibility or more of the same? Only a new responsibility is a finding.
Sketch the split in one sentence.

## Lens C: Dependency direction and cycles

| Signal | Threshold |
| --- | --- |
| First edge between two packages | 0 imports either way on base |
| New 2-cycle | a one-way pair becomes mutual (adding to an already-mutual pair is a note, not a candidate) |
| Stable to volatile edge | from I ≤ 0.30 to I ≥ 0.85, with I = out/(in+out) on base |
| Module enters an import cycle | joins or creates an SCC |
| File coupling | ≥ 8 distinct `infrahub.*` packages imported, base below |

Ask: does the edge contradict the reference frame? Trace one step further: does the target already
import something that imports the source? Name the cycle it is about to close. Without a frame, a
direction finding becomes an open question instead.

## Lens D: Functional sense

Is there a domain reason, stated in the pull request or visible in the code, why feature A now needs
feature B? If the pull request states it, drop the candidate or downgrade it to a note. Would a user
of A be surprised to find B on its path, at startup, in its failure modes, or in its permissions?
