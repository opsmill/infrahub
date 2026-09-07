# Phase 0 Research: Prefect's effective related-resources limit

All findings below were verified empirically against the Prefect version pinned in this repository
(**prefect 3.7.5**, Python 3.14), not taken from documentation. Each claim names the command or
source file that established it.

## R1. Which accessor does Prefect itself enforce the cap with?

**Decision**: mirror Prefect's own validator exactly — `PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES.value()`.

Prefect rejects over-sized events in `_validate_related_resources`
(`.venv/.../prefect/events/schemas/events.py:103-111`), attached as an `AfterValidator` to
`Event.related`:

```python
def _validate_related_resources(value) -> List:
    from prefect.settings import PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES

    if len(value) > PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES.value():
        raise ValueError(
            "The maximum number of related resources "
            f"is {PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES.value()}"
        )
    return value
```

**Rationale**: this is the strongest available answer to FR-004. The spec asks Infrahub's number to
equal the number Prefect enforces. Reading *the very same accessor Prefect's validator reads* makes
divergence structurally impossible rather than merely unlikely — any future change to how Prefect
resolves this value is inherited automatically. It also documents itself: the reader can see the
Infrahub cap and the Prefect check are the same expression.

**Alternatives rejected**:

- `get_current_settings().server.events.maximum_related_resources` — equivalent today (verified
  identical under both `temporary_settings` overrides, below), but it reaches through a nested
  settings path that Prefect's own validator does not use. It restates the lookup instead of
  sharing it, so it could drift if Prefect re-homes the field.
- The raw `os.environ` read in place today — misses every non-environment configuration source.
  See R3.

**Non-deprecated**: importing and calling both accessors emits no `DeprecationWarning` (checked with
`warnings.catch_warnings(record=True)` and `simplefilter("always")`; the only deprecation surfaced
under `-W error` came from an unrelated third-party import, `coolname`'s use of `codecs.open`).

## R2. What is Prefect's own default?

**100**, confirmed three ways:

- `PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES.value()` returns `100` with nothing configured.
- `ServerEventsSettings.model_fields["maximum_related_resources"].default` is `100`.
- `get_current_settings().server.events.maximum_related_resources` is `100`.

The repository's shipped image sets `PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES=500`
(`development/Dockerfile:129`) — the only place 500 legitimately belongs, and it stays untouched
(FR-006).

## R3. Are the two environment-variable names really aliases?

**Yes — one setting, two accepted names.** The field's validation alias is:

```text
AliasChoices(choices=[AliasPath(path=['maximum_related_resources']),
                      'prefect_server_events_maximum_related_resources',
                      'prefect_events_maximum_related_resources'])
```

Verified end-to-end by launching a fresh interpreter per case:

| Configured at process start | `PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES.value()` |
|---|---|
| nothing | 100 |
| `PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES=500` | 500 |
| `PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES=250` | 250 |

Both accessors also agree under either override:
`temporary_settings({PREFECT_SERVER_...: 500})` → both report 500;
`temporary_settings({PREFECT_EVENTS_...: 250})` → both report 250.

**Consequence**: honouring the *setting* honours both names automatically. No per-name handling is
needed, which satisfies FR-004 without enumerating aliases — and without Infrahub having to track
alias changes.

## R4. How is the value driven at test time? (this one changes the tests)

**`temporary_settings` works; `monkeypatch.setenv` does not.**

Prefect resolves settings from the environment **once**, when the settings object is constructed at
import. Mutating `os.environ` afterwards has no effect:

```text
unset                              -> 100
os.environ[...PRIMARY...] = '300'  -> 100   # still 100
os.environ[...ALIAS...]   = '250'  -> 100   # still 100
```

whereas `temporary_settings({PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES: 500})` yields `500`
inside the context and `100` after it.

**This is the single highest-impact finding for the work.** The existing
`backend/tests/unit/event/test_limits.py` drives every one of its cases with
`monkeypatch.setenv(ENV_VAR, ...)`, which works *only* because the current implementation reads
`os.environ` live on each call. The moment the implementation reads the Prefect setting, all of
those cases silently stop exercising what they claim to: they would each fall through to the
default and the parametrized expectations would fail.

So the test migration is **not optional polish** — it is a required part of the change. Every case
must move to `temporary_settings`. The upstream feature description flagged this as "verify
empirically which mechanism actually drives the new implementation"; the answer is `temporary_settings`,
and the tests must express that.

Note that `test_event_on_the_budget_survives_the_prefect_run_context_append` in that file already
wraps its body in `temporary_settings` *in addition to* `monkeypatch.setenv` — it needed the real
setting to make Prefect's own validator agree. After this change the `setenv` half of that pairing
becomes dead weight and should go, leaving `temporary_settings` as the single mechanism.

Production is unaffected by the import-time snapshot: deployments set the environment variable
before the process starts (R3 row 2 verified exactly that path), so the shipped image still reads
500.

## R5. Which defensive branches survive?

The current code guards two failure classes. Under the new accessor they are no longer symmetric,
because `.value()` returns an **already-Pydantic-validated `int`**.

| Configured value | What Prefect does | Reachable in Infrahub? |
|---|---|---|
| `abc` (non-numeric) | raises `pydantic_core.ValidationError` for `ServerEventsSettings.maximum_related_resources` while *constructing settings* — i.e. at import, before Infrahub code runs | **No.** The process cannot start; there is nothing to fall back from. |
| `0` | accepted, `.value()` → `0` | **Yes.** |
| `-5` | accepted, `.value()` → `-5` | **Yes.** |

**Decisions**:

- **Drop the parse guard.** The `try/except ValueError` around `int(raw_value)` becomes unreachable
  dead code. This is a deliberate, and better, behaviour change: a typo in an operator's
  environment now fails **loudly at startup inside Prefect** instead of silently degrading to a
  wrong cap — which is exactly the class of silence this card exists to remove. Keeping an
  unreachable `except` would imply a fallback that cannot happen. Called out in the changelog.
- **Keep the non-positive guard.** `0` and `-5` are reachable, and a negative maximum would make
  the derived budget and chunk-size arithmetic meaningless.

  Be precise about what this guard does and does not achieve: with a maximum of `0`, Prefect's
  validator rejects *every* event with any related resource (`len(related) > 0`), so falling back
  to 100 does **not** rescue delivery — nothing Infrahub does can. Its purpose is narrower: keep
  the derived numbers sane and positive rather than deriving a budget from a negative ceiling. The
  existing `max(1, ...)` floors in `get_related_resource_budget` and `get_submission_chunk_size`
  already protect the arithmetic; this guard keeps the *input* sensible too, and keeps the module's
  current documented contract ("falling back when the value is not a positive number") true.

## R6. Consumers and blast radius

`get_prefect_max_related_resources()` is not called directly by production code. Two derived
helpers front it, and only their values reach callers:

| Helper | Production consumers |
|---|---|
| `get_related_resource_budget()` | `events/node_action.py` (truncates `NodeMutatedEvent.get_related()`), `events/group_action.py` (imports it) |
| `get_submission_chunk_size()` | `computed_attribute/tasks.py`, `core/merge/recompute_coalescing.py` |

No signature changes anywhere (FR-007) — only the number these helpers compute changes, and only on
deployments that did not configure the limit. Test files touching this surface:
`backend/tests/unit/event/test_limits.py`, `test_node_action.py`, `test_group_action.py`, and
`backend/tests/unit/core/merge/test_submit_coalesced_recompute.py`.

Note `group_action.py` imports the budget helper but, per issue #10127, does not actually bound its
own related list — that is the separate defect the issue is primarily about, explicitly out of
scope here (see spec "Out of Scope").

## R7. Behaviour delta summary

| Deployment | Before | After |
|---|---|---|
| Shipped image (`=500`) | max 500, budget 450 | **unchanged** — max 500, budget 450 |
| No configuration | max 500, budget 450 → Prefect rejects at 100, **events silently lost** | max 100, budget 80 → events delivered |
| Alias name configured | ignored → wrong cap | honoured |
| Prefect profile / config file | ignored → wrong cap | honoured |
| Malformed value | silently treated as 500 | **fails loudly at startup** (Prefect `ValidationError`) |
| `0` / negative | falls back to 500 | falls back to 100 |

## R8. Environment gotcha when reproducing in a fresh worktree

Recorded because it cost real time and is invisible from the code.

A fresh `git worktree` does **not** populate submodules, so `python_sdk/` starts empty. If
`uv sync` runs in that state, hatch builds the editable install with the `python_sdk/infrahub_sdk`
→ `infrahub_sdk` source mapping **silently skipped**, and the resulting
`.venv/.../_editable_impl_infrahub_server.pth` lists only `backend` and `python_testcontainers`.
Every import of `infrahub.events.limits` then dies with `ModuleNotFoundError: No module named
'infrahub_sdk'` — because `infrahub/events/__init__.py` reaches `lock.py` → `config.py` →
`infrahub_sdk.utils`.

Initialising the submodule afterwards is not enough: `uv sync` reports "Checked 229 packages" and
changes nothing, because the package's own version is unchanged. The editable install must be
rebuilt explicitly:

```bash
git submodule update --init python_sdk
uv sync --all-groups --reinstall-package infrahub-server
```

After that the `.pth` carries all three paths and both `uv run python` and `uv run pytest` work.
`PYTHONPATH=python_sdk` also works as a one-off workaround but does not fix the environment.

**Baseline established after the fix**: `uv run pytest backend/tests/unit/event/
backend/tests/unit/core/merge/test_submit_coalesced_recompute.py` → **59 passed**. That is the
number the change must preserve, plus its new cases.
