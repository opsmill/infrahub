# User and Global Preferences

> Part of: `dev/knowledge/backend/` | Related: [permissions.md](permissions.md), [mutations.md](mutations.md), [query-pattern.md](query-pattern.md), [package-init-files.md](package-init-files.md)

Preferences store per-user and organisation-wide client settings (currently `date_format` and
`timezone`). They are internal `StandardNode` objects, not schema nodes: they are not versioned by
branch, not exposed through the generic node API, and carry no schema relationships. All access goes
through a small backend module (`backend/infrahub/core/preferences/`) and a dedicated GraphQL
surface.

## Data model

A single `Preference` model holds both layers. The layer is identified only by `owner_id`:

| `owner_id` | Layer | Meaning |
|------------|-------|---------|
| an account id (UUID) | USER | that account's own overrides |
| `GLOBAL_OWNER_ID` (`"__global__"`) | GLOBAL | the organisation-wide defaults |

The global owner id is a fixed sentinel string rather than a real node id. Accounts are UUID-keyed,
so the sentinel can never collide with a user's owner id, and the global row needs no link to any
node in the graph. It is persisted, so it is a stable key.

Fields:

| Field | Type | Notes |
|-------|------|-------|
| `owner_id` | `str` | plain string, not a graph relationship |
| `date_format` | `DateFormat` enum, nullable | a semantic key (e.g. `ISO_DATETIME`), not a render pattern; each client maps the key to its own formatter |
| `timezone` | `str` (IANA name), nullable | currently accepts any string; no backend validation |

`date_format` is enum-typed, so an unknown key is rejected at construction, including when a row is
loaded from the database. It round-trips as a plain string because the enum subclasses `str`.

## Reads never create a row

Every read path treats a missing row as "nothing set". A read never writes. The write path (the set
mutation) is the only path that ever creates a `Preference` row. The read methods live on
`PreferenceRepository`:

| Method | Returns |
|--------|---------|
| `get_for_owner(owner_id)` | the row for one owner, or `None` |
| `get_for_owners(owner_ids)` | a `{owner_id: Preference}` map, in one query; owners with no row are absent |
| `get_all()` | every row, across all owners |

The Cypher lives in `core/query/preference.py` (`PreferenceGetByOwnerQuery`, `PreferenceGetAllQuery`),
sharing a common read/deserialization base. Rows are ordered by `uuid` so reads are stable even in
the (lock-prevented) event of a duplicate.

## Effective resolution

`EffectivePreferences` resolves each field independently across the two stored layers:

1. USER value if the user layer sets it, else
2. GLOBAL value if the global layer sets it, else
3. DEFAULT with a null value.

Resolution is per attribute, so a single read can return one attribute from USER and another from
GLOBAL. Each resolved field is a `ResolvedPreference(value, source)`. A DEFAULT source carries a null
value: the backend does not know the clients' built-in defaults, it only reports that neither layer
sets the field.

## Write path

Writes go through the `InfrahubSetPreferences` mutation, which targets one scope (`USER` or
`GLOBAL`) and performs a lazy upsert:

- `USER` writes the calling account's own row (`owner_id = account_session.account_id`). There is no
  account argument, so there is no path to write another user's preferences.
- `GLOBAL` writes the sentinel-owned row after the permission gate (below).

Two argument states are distinguished: an omitted field is left unchanged (an internal `_UNSET`
sentinel), while an explicit `null` resets the field.

The read-modify-write runs inside a per-owner distributed lock keyed on `owner_id`
(`PREFERENCE_LOCK_NAMESPACE`). Without it, concurrent first-writes for the same owner could each
observe "no row" and create a duplicate, and concurrent updates could lose writes. The read runs
inside the lock so it observes any in-flight write for the same owner. Distinct owners never contend.

This lock is an invariant, not an implementation detail of the upsert: **every path that mutates
Preference rows — deletes included — must acquire the same per-owner lock**, because a mutation
running outside it can interleave with the read-then-save above (e.g. a delete slipping between the
read and the save gets silently undone by the save).

## Permissions

| Path | Requirement |
|------|-------------|
| `InfrahubEffectivePreferences` (query) | any authenticated caller |
| `InfrahubUserPreferences` (query) | any authenticated caller; account-bound to their own row |
| `InfrahubGlobalPreferences` (query) | `manage_global_preferences` |
| `InfrahubSetPreferences` scope=`USER` | any authenticated caller; own row only |
| `InfrahubSetPreferences` scope=`GLOBAL` | `manage_global_preferences` |

`manage_global_preferences` is a global permission enforced imperatively with
`raise_for_permission()` in the resolver, before any read (fail-closed), not through the kind-based
checker pipeline. Super admins pass implicitly. USER paths need no permission because they only ever
touch the calling account's own row.

## GraphQL surface

| Operation | Shape |
|-----------|-------|
| `InfrahubEffectivePreferences` | merged values, each as `{ value, source }` |
| `InfrahubUserPreferences` | the caller's own raw values, null where unset |
| `InfrahubGlobalPreferences` | organisation-wide raw values, null where unset |
| `InfrahubSetPreferences` | upsert one scope; returns the written values |

The effective view carries a `source` per field; the raw views do not, because the scope is the
source.

## Caveats

- **Orphan rows.** A `StandardNode` cannot declare an `on_delete: cascade` schema relationship, so
  the schema cannot cascade a `Preference` row when its account is deleted. Instead the account-delete
  mutation drops the row explicitly, best-effort and under the per-owner preference lock.
  A deletion path that bypasses the mutation still leaves the row behind; that orphan is benign:
  account ids are UUIDs and are never reused, so it is permanently unreachable.
- **`Optional[X]` on the model.** Persisted nullable fields use `Optional[X]` rather than `X | None`
  because of how `StandardNode.guess_field_type` works on Python before 3.14.
