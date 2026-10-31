# Choosing tests

Use this guide when adding a test or reviewing overlapping coverage. The
[testing standards](../../guidelines/backend/testing.md) define the rules; the
[infrastructure reference](../../knowledge/backend/testing.md) describes the available fixtures.

## State the behavior

Write down the input or starting state, the operation, and its observable result. Name a plausible
regression that would make the assertion fail. For example: a cleanup deletes expired finished runs
and leaves unfinished runs in storage. A test that only checks that the cleanup returns successfully
does not establish either result.

Find the existing tests through the code's callers. A query may be covered by a resolver test that
never mentions its class. Read the assertions and fixtures before deciding that coverage is missing.

## Choose unit or component coverage

Ask whether the result depends on the real collaborator's behavior.

| What must be verified? | Where to test it | What the assertion observes |
|------------------------|------------------|-----------------------------|
| Parsing, validation, arithmetic, or a decision over supplied values | Unit | A concrete output or error for those inputs |
| A retry policy responding to HTTP errors | Unit, using a scripted transport and injected clock | Requests, retry boundaries, progress, and final outcome |
| A policy deciding which tables need rewriting from supplied size measurements | Unit, using a recording rewriter | Selected tables and reported outcomes |
| A query selecting and deleting eligible rows | Component, using the real database | Stored rows before and after the operation, including rows that must remain |
| A route connecting validation, job execution, and persistence | Component | The response and the resulting persisted state |
| PostgreSQL locks, transaction rollback, or table rewrites | Component with PostgreSQL, or the existing Docker integration suite when the service boundary matters | The database's actual behavior |
| A command reaching a deployed worker and reporting its result | Integration Docker | The command's result and the effect in the running service |

An in-process HTTP client or several cooperating Python objects do not require a component test by
themselves. Conversely, SQLite-backed tests are component tests even without a network connection.
An adapter can prove how the caller reacts to a failure; it cannot prove that a database issues that
failure, commits a transaction, or enforces a lock correctly.

For a database query, execute the query and assert its returned data at the component layer. A unit
test that assigns fabricated driver rows and checks a trivial accessor cannot detect a broken query.
If the returned rows undergo an independently complex transformation, cover that transformation's
cases in unit tests and keep the component assertion on real query output.

For a policy test, remove unrelated setup. If a rewrite decision only uses supplied table sizes,
calling deletion and seeding old runs first adds database work without testing the decision better.
Initialize the job's input state directly and test deletion separately against storage. Keep the
route or job-runner test that proves deletion and rewriting are connected correctly.

## Review overlapping tests

Compare the scenario, production path, collaborators, and assertions of each candidate. Use this
question: **Which plausible failure would this test detect that the retained tests would miss?**
Also consider whether a focused test isolates a complex failure that a broader test would obscure.
Do not use a test count or line-coverage percentage as the answer.

| Candidate pair | Decision |
|----------------|----------|
| Same setup and call, with one test's assertions fully covered by the other | Remove the duplicate if it adds no useful focused diagnosis |
| Same assertion structure, different boundary or error category | Parameterize and retain the distinct cases |
| Unit policy matrix plus one route exercising the real policy and database | Keep both: one checks decisions, the other checks integration |
| Full policy matrix repeated through the client, command, route, and deployed stack | Keep each matrix at its owning layer; retain representative wiring and layer-specific failures above it |
| Unit accessor over fabricated query rows plus component test of the same returned field | Keep the real query assertion |
| Client retry test plus CLI output/exit-code test | Keep both when the CLI adds assertions on presentation or exit behavior |

For example, connection loss and HTTP 502, 503, and 504 can share one recovery test body. They remain
distinct cases because changing the error classification can affect one without the others. A CLI
test for each of those errors is unnecessary when they all become the same wait reason and the CLI
only renders that reason. Retain a representative rendering test and the client classification cases.

Parameterization reduces repeated code, not the number of behaviors to verify. Avoid a Cartesian
product of options unless their interaction can change the result. Keep boundary values and cases
that take different decisions; remove additional examples of the same equivalence class when they
add no new assertion.

## Check what the doubles prove

Inject adapters at existing boundaries. Do not patch out the behavior being tested or add production
hooks solely to observe it. Recording and failing adapters are useful for caller decisions, while
real component tests verify the adapter's infrastructure behavior.

A scripted transport that returns the next response regardless of the request can accept an
incorrect URL or method. When the protocol matters, assert the complete request sequence and payloads,
not only the request count. Use an injected clock for retry deadlines so tests do not wait in real time.

Keep expected values independent of the implementation. A test that computes its expected output
using the same serializer or formula can pass with the same defect on both sides of the comparison.
See [Assert exact expectations](../../guidelines/backend/testing.md#assert-exact-expectations).

## Running integration_docker tests locally

Repo-based `tests/integration_docker/` tests build throwaway git repositories with dulwich (`porcelain.commit`), which honors your global `commit.gpgsign` setting. If you sign commits and the `gpg` Python bindings (gpgme) are not installed — common on macOS — repository setup fails with a misleading `ModuleNotFoundError: No module named 'gpg'`. That takes down every repo-based test plus any test that depends on the repo, showing up as cascading, confusing assertion failures.

These tests never need signed commits. Disable signing for the run by pointing git's config at `/dev/null`:

```bash
GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null uv run pytest backend/tests/integration_docker/<file>
```

With an empty config `commit.gpgsign` defaults to off, and dulwich falls back to your OS username/host for the commit author, so no `[user]` block is needed. CI does not sign commits, so this only affects local runs.

## Verify the cleanup

Before deleting a test, identify the retained test and the assertion that replaces it. When moving
one to unit, confirm its fixtures no longer start a service, migrate a database, or open a connection.
Imports and constructing a lazy collaborator alone do not prove infrastructure behavior.

Run the affected unit and component modules. For an assertion intended to prevent a regression,
temporarily reintroduce the faulty behavior and confirm the test fails for the intended reason;
restore it before committing. Record that evidence and the retained coverage in the PR description.
