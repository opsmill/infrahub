# Contract deltas

## GraphQL

```graphql
enum InstanceColor { RED AMBER GREEN BLUE INDIGO PURPLE GRAY }

# Only the global query exposes the two fields.
type GlobalPreferencesType {
  date_format: DateFormat
  timezone: String
  instance_label: String
  instance_color: InstanceColor
}

type Query {
  InfrahubGlobalPreferences: GlobalPreferencesType   # was RawPreferencesType
}

type Mutation {
  InfrahubSetPreferences(
    scope: PreferenceScope!
    date_format: DateFormat
    timezone: String
    instance_label: String        # new; omitted = unchanged, null = reset
    instance_color: InstanceColor # new; omitted = unchanged, null = reset
  ): InfrahubSetPreferences
}

type InfrahubSetPreferences {
  ok: Boolean
  date_format: DateFormat
  timezone: String
  instance_label: String   # new
  instance_color: InstanceColor # new
}
```

Errors:
- `scope: USER` with `instance_label` or `instance_color` provided → `ValidationError` "instance_label and instance_color can only be set with scope GLOBAL" before any read.
- `instance_label` longer than 32 characters after trimming, or containing a line break → `ValidationError` naming the rule; nothing stored.
- A color outside the enum → the GraphQL enum coercion error listing the members; nothing stored.
- Missing `manage_global_preferences` on `scope: GLOBAL` → the existing permission error; nothing stored.

## REST `GET /api/config` (public)

```json
{
  "main": {},
  "logging": {},
  "analytics": {},
  "experimental_features": {},
  "sso": {},
  "ldap": {},
  "installation_type": "",
  "policy": {},
  "instance": { "label": "us-east-1 PROD", "color": "RED" }
}
```

`instance.label` and `instance.color` are `null` when unset. Reading never creates the preference row.
