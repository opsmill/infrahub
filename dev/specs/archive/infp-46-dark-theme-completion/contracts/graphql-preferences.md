# Contract: GraphQL preferences — theme field

**Feature**: [spec.md](../spec.md) | **Covers**: FR-001, FR-002, FR-003, FR-004

Additive delta to the existing preferences surface. Every change mirrors how `date_format` is already
modelled, so nothing below introduces a pattern the schema does not already use.

⚠ `schema/schema.graphql` is generated and CI-validated (`uv run invoke docs.validate`). Regenerate
with `uv run invoke schema.generate-graphqlschema` and commit, or CI fails on a stale file.

⚠ GraphQL schema modifications are **Ask First** per `AGENTS.md`. This contract is a proposal
requiring sign-off, not an approved change.

## New enum

```graphql
"""
Appearance choices. SYSTEM follows the operating system; the dark palette is pre-release.
"""
enum Theme {
  LIGHT
  DARK
  SYSTEM
}
```

⚠ The description **must stay on one line** in the Python source. `graphql-core`'s SDL printer
dedents multi-line descriptions differently across versions, which makes the generated
`schema.graphql` environment-dependent — a constraint already documented in
`backend/infrahub/graphql/types/preferences.py`.

## New effective-value type

```graphql
"""An effective `theme` value and the source it was resolved from."""
type EffectiveTheme {
  source: PreferenceSource!
  value: Theme
}
```

`value` is null when nothing is stored at any layer; `source` is then `DEFAULT` and the client
substitutes the deployment default from the config payload.

## Changed types

```diff
 type EffectivePreferencesType {
   date_format: EffectiveDateFormat!
   timezone: EffectiveTimezone!
+  theme: EffectiveTheme!
 }

 type RawPreferencesType {
   date_format: DateFormat
   timezone: String
+  theme: Theme
 }
```

`EffectivePreferencesType.theme` is non-null (the wrapper always exists); the `value` inside it is
nullable. That is the existing convention — the wrapper reports a source even when there is no value.

## Changed mutation

```diff
-InfrahubSetPreferences(date_format: DateFormat, scope: PreferenceWriteScope!, timezone: String): InfrahubSetPreferences
+InfrahubSetPreferences(date_format: DateFormat, scope: PreferenceWriteScope!, theme: Theme, timezone: String): InfrahubSetPreferences
```

The payload gains a matching `theme: Theme` output field.

### ⚠ Three-state argument semantics

`InfrahubSetPreferences` distinguishes three cases via the `_UNSET` sentinel in
`backend/infrahub/graphql/mutations/preferences.py`. `theme` must honour all three, and a naive
`theme: Theme | None = None` parameter collapses the first two and makes clearing impossible:

| Client sends | Meaning | Stored |
|---|---|---|
| argument omitted | leave untouched | unchanged |
| `theme: null` | clear the override at this scope | `None` |
| `theme: DARK` | set the override | `Theme.DARK` |

Mirror the existing handling exactly:

```python
if theme is not _UNSET:
    preference.theme = None if theme is None else ThemeEnum(theme)
```

## Behavioural contract

⚠ The `GLOBAL` rows describe the **backend resolution chain**, which is shared across all
preference fields and therefore accepts a global theme write. No interface offers one in this
version — theme is user-scoped only (FR-003), achieved by leaving `theme` out of the
global-preferences mutation document, so the global layer simply has no writer. The rows exist
because the chain must keep resolving correctly through a layer that is always `null` today and
gains a writer only when the organisation-wide default ships later.

| Given | When | Then |
|---|---|---|
| No preference at any layer | `InfrahubEffectivePreferences` queried | `theme.value = null`, `theme.source = DEFAULT` |
| Global set to `DARK`, no user value | queried | `theme.value = DARK`, `theme.source = GLOBAL` |
| Global `DARK`, user `LIGHT` | queried | `theme.value = LIGHT`, `theme.source = USER` |
| User `LIGHT` | mutation with `theme: null`, scope `USER` | user override cleared; next query resolves to global or default |
| Any state | mutation omitting `theme` | `theme` unchanged; other supplied fields still written |
| Caller lacks global-write permission | mutation with scope `GLOBAL` | rejected by the existing permission check; no new permission introduced |
| Stored value not a `Theme` member | read from database | rejected at construction, as `date_format` already behaves |

## Out of scope for this contract

- The deployment default — it is not a preference and is not served over GraphQL. See
  [rest-config.md](./rest-config.md).
- Stage-2 resolution of `SYSTEM` to a concrete palette. The server returns the stored choice; only
  the client can observe the operating system's appearance.
