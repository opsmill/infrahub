# Quickstart: verifying the related-resources limit fix

All commands run from the repository root.

## 1. The defect, before the fix

Show that Infrahub's ceiling and Prefect's enforced ceiling disagree when nothing is configured:

```bash
uv run python -c "
from prefect.settings import PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES as P
from infrahub.events.limits import get_prefect_max_related_resources, get_related_resource_budget
print('prefect enforces :', P.value())
print('infrahub believes:', get_prefect_max_related_resources())
print('infrahub budget  :', get_related_resource_budget())
"
```

**Before**: `prefect enforces : 100`, `infrahub believes: 500`, `infrahub budget  : 450`.
An event built up to that 450 budget is rejected by Prefect's own validator and silently dropped.

**After**: all three agree — `100`, `100`, `80`.

## 2. The shipped image is unaffected

The image sets the variable, so reproduce that path in a fresh interpreter (the value must be in the
environment *before* the process starts — Prefect snapshots settings at import):

```bash
PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES=500 uv run python -c "
from infrahub.events.limits import get_prefect_max_related_resources, get_related_resource_budget, get_submission_chunk_size
print(get_prefect_max_related_resources(), get_related_resource_budget(), get_submission_chunk_size())
"
```

Expect `500 450 250` — identical before and after the change.

## 3. The alias and Prefect's own settings are honoured

Only the second of these works before the fix; both work after:

```bash
PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES=250 uv run python -c "
from infrahub.events.limits import get_prefect_max_related_resources as m; print('alias env  ->', m())"

uv run python -c "
from prefect.settings import PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES as S, temporary_settings
from infrahub.events.limits import get_prefect_max_related_resources as m
with temporary_settings({S: 300}): print('settings   ->', m())"
```

Expect `250` and `300`.

## 4. Non-positive values fall back

```bash
PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES=0 uv run python -c "
from infrahub.events.limits import get_prefect_max_related_resources as m; print('zero ->', m())"
```

Expect `100`. (Note: with Prefect's own maximum at 0 it rejects every event with related resources
regardless — this guard only keeps the derived arithmetic sane. See research.md R5.)

## 5. A malformed value now fails loudly

```bash
PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES=abc uv run python -c "
import infrahub.events.limits"
```

Expect a Prefect/Pydantic `ValidationError` at import. Before the fix this was silently treated as
500. This is an intentional behaviour change (plan.md D2).

## 6. Test suite and lint gates

```bash
uv run pytest backend/tests/unit/event/ backend/tests/unit/core/merge/test_submit_coalesced_recompute.py
uv run invoke format
uv run invoke lint
grep -n '500' backend/infrahub/events/limits.py   # must print nothing
git diff --stat origin/develop...HEAD -- development/Dockerfile   # must be empty
```

## 7. Optional: the end-to-end silent-drop check

Confirms an event built on the budget survives Prefect's validator with nothing configured — the
condition that fails today:

```bash
uv run python -c "
from prefect.events.schemas.events import Event, RelatedResource, Resource
from infrahub.events.limits import get_related_resource_budget
Event(event='infrahub.node.updated',
      resource=Resource({'prefect.resource.id': 'infrahub.node.abc'}),
      related=[RelatedResource({'prefect.resource.id': f'infrahub.node.{i}',
                                'prefect.resource.role': 'infrahub.related.node'})
               for i in range(get_related_resource_budget())])
print('accepted by Prefect')
"
```

**Before**: `ValueError: The maximum number of related resources is 100`.
**After**: `accepted by Prefect`.
