# User and Global Preferences

> Part of: `dev/knowledge/backend/` | Related: [permissions.md](permissions.md), [mutations.md](mutations.md), [query-pattern.md](query-pattern.md), [package-init-files.md](package-init-files.md)

Preferences store per-user and organisation-wide client settings: `date_format` and `timezone` on
both layers, `instance_label` and `instance_color` on the global layer only. They are internal
`StandardNode` objects, not schema nodes: they are not versioned by branch, not exposed through the
generic node API, and carry no schema relationships. All access goes through a small backend module
(`backend/infrahub/core/preferences/`) and a dedicated GraphQL surface.

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
| `timezone` | `str` (IANA name), nullable | validated at write, not on the model (see below) |
| `instance_label` | `str`, nullable | global row only; trimmed, at most `INSTANCE_LABEL_MAX_LENGTH` (32) characters, no control character; validated at write only |
| `instance_color` | `InstanceColor` enum, nullable | global row only; one of `RED`, `AMBER`, `GREEN`, `BLUE`, `INDIGO`, `PURPLE`, `GRAY` |

`date_format` is enum-typed, so an unknown key is rejected at construction, including when a row is
loaded from the database. It round-trips as a plain string because the enum subclasses `str`.

`timezone` is validated on the **write path only**, never on the model. A model-level validator
would run on every read (rows are reconstructed from the database), and since user and global rows
are fetched together, one bad stored value would break effective-preference reads for every user.
The set mutation validates a provided timezone by resolving it against the runtime's zone database
(construction, not an enumerated allowlist — so backward-compatibility aliases a client offers are
accepted) and normalizes an empty value to unset so the write reply agrees with later reads. Reads
stay lenient, so any value stored before this validation existed is still returned as-is.

`instance_label` follows the same rule: `validate_instance_label` runs in the set mutation only. It
strips surrounding whitespace, turns an empty result into unset, and rejects a control character
(Unicode category `Cc`, which covers line breaks, tabs and NUL, plus the bidirectional controls
U+202A–U+202E and U+2066–U+2069) or more than 32 characters with a `ValidationError` that names the
rule. A stored value never breaks a read.

`instance_color` needs no validator of its own: the GraphQL enum rejects an unknown member with a
message that lists the allowed ones, and Pydantic does the same on the REST model. Each member's name
equals its value (`RED = "RED"`) on purpose: graphene puts member *names* on the GraphQL wire while
Pydantic serialises *values* on REST, so the equality keeps `schema.graphql`, `openapi.json` and the
two generated TypeScript types in agreement. Renaming a member later needs a data migration, because
the value is what is stored.

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

`instance_label` and `instance_color` are accepted with `scope: GLOBAL` only. When either argument is
provided with `scope: USER`, the mutation raises a `ValidationError` before any read or lock, so no
user row is created or touched. A per-user row therefore never holds either field, even though the
model declares them.

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
| `InfrahubGlobalPreferences` | organisation-wide raw values, null where unset, plus `instance_label` and `instance_color` |
| `InfrahubSetPreferences` | upsert one scope; returns the written values |

The effective view carries a `source` per field; the raw views do not, because the scope is the
source.

`InfrahubGlobalPreferences` returns `GlobalPreferencesType`, a subclass of the raw type that adds the
two instance fields. The user and effective queries keep the base types, so selecting
`instance_label` on them fails at query validation ("Cannot query field"). This is what keeps the
fields off the per-user surface; `EffectivePreferences` is unchanged.

## Public read through `/api/config`

Every client, the login page included, loads `GET /api/config` before it renders, and that response
is the only way an anonymous visitor reads the instance label and color. The response carries two
`InstanceIdentityAPI(label, color)` values:

- `instance_defaults`: the deployment defaults from `InstanceSettings` (`INFRAHUB_INSTANCE_LABEL`,
  `INFRAHUB_INSTANCE_COLOR`, or the `[instance]` section of `infrahub.toml`).
- `instance`: the effective identity, built in `get_instance_identity`. Each field is resolved on its
  own: the value of the global row from `PreferenceRepository.get_for_owner(GLOBAL_OWNER_ID)` if set,
  else the deployment default, else `null`.

The read goes through the repository, so it never creates the global row. Any exception on that
read is logged and `instance` is served with a null label and color, because the config response
bootstraps every page and the login page must not fail with the identity. The defaults are not
served in that case: a default can name another stage than the saved value it would stand in for. Only these fields are exposed;
`date_format` and `timezone` stay behind the authenticated GraphQL queries.

The deployment defaults never reach the GraphQL surface: `InfrahubGlobalPreferences` returns the
saved values only, so the form can tell a saved value from a default. Resetting a saved value (an
explicit `null` in the set mutation) makes the default apply again.

The settings validate both values when they load: the label goes through `validate_instance_label`,
and an empty color counts as unset because a deployment tool can pass an unset variable as an empty
string. The color is also uppercased, so `red` is accepted. An invalid value stops the process at
startup with a message that names the environment variable. The enum, the length limit and the label
validator live in `infrahub/instance_identity.py`, not under `core/preferences/`, because
`config.py` imports them and anything under `infrahub.core` imports `config.py` back through
`core.registry`.

## Caveats

- **Orphan rows.** A `StandardNode` cannot declare an `on_delete: cascade` schema relationship, so
  the schema cannot cascade a `Preference` row when its account is deleted. Instead the account-delete
  mutation drops the row explicitly, best-effort and under the per-owner preference lock.
  A deletion path that bypasses the mutation still leaves the row behind; that orphan is benign:
  account ids are UUIDs and are never reused, so it is permanently unreachable.
- **`Optional[X]` on the model.** Persisted nullable fields use `Optional[X]` rather than `X | None`
  because of how `StandardNode.guess_field_type` works on Python before 3.14.
