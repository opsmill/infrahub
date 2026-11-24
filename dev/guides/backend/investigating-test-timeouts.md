# Investigating test timeouts

Treat a timeout as a performance investigation as well as a correctness failure. Keep the test and
its assertions enabled, and spend time finding and reducing unnecessary work before proposing a
larger timeout. Use the [testing standards](../../guidelines/backend/testing.md) and
[infrastructure reference](../../knowledge/backend/testing.md) when changing fixtures.

## Locate the time spent

Identify whether the timeout occurred during setup, the test body, or teardown. Collect phase and
fixture durations, then trace the slow phase into database queries, service startup, polling, and
cleanup. For a stalled async test, capture suspended coroutine await chains and service diagnostics;
a thread stack showing an idle event loop does not identify the operation it awaits.

Compare a failing attempt with a passing attempt on the same commit. Reproduce the preceding tests,
worker count, and resource load where practical. Record differences from CI, including dependency
versions and container configuration. Separate slow progress from a blocked operation: less setup
work can reduce contention without fixing a deadlock.

## Reduce work without weakening coverage

Measure a baseline, identify the dominant cost, and make one targeted change. Check for repeated
schema persistence and reloads, unused fixtures, oversized datasets, repeated queries, and waits
that continue after the required state is ready. Reuse existing lightweight fixtures when they
establish the same starting state. Preserve real persistence and service interactions when the
assertions depend on them.

Keep isolation intact: sharing a mutable database across tests or workers can create new races.
Retain every distinct assertion and failure mode. Do not skip, quarantine, mark as expected failure,
or deselect the test to make the suite pass. Do not add blind retries or sleeps. Increase a deadline
only when measurements establish that the necessary work legitimately exceeds it after optimization.

## Verify the result

Compare setup, body, teardown, and total duration under matching conditions. Report measurements in
the pull request; do not add assertions on host execution speed to the test suite. Where appropriate,
verify that a deliberately broken implementation still fails the optimized test.

Run the affected tests repeatedly with assertions enabled and include the preceding tests when
investigating order dependence. Report executed passes, failures, and skips separately. State whether
the original timeout reproduced locally, what work was removed, and what remains unexplained.
A faster local pass is evidence of an optimization, not proof that a CI-only stall is fixed.

If the cause remains unknown, keep coverage enabled and submit diagnostics or investigation findings
that will identify the blocked operation on its next failure.
