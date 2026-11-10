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
  InfrahubGlobalPreferences: GlobalPreferencesType!   # was RawPreferencesType!
}

type Mutation {
  InfrahubSetPreferences(
    scope: PreferenceWriteScope!
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
- `instance_label` longer than 32 characters after trimming, or containing a control character (line break, tab, NUL, the line and paragraph separators U+2028 and U+2029, bidirectional text control) → `ValidationError` naming the rule; nothing stored.
- A color outside the enum → the graphql-core enum coercion error `Variable '$instance_color' got invalid value '<x>'; Value '<x>' does not exist in 'InstanceColor' enum.`, followed by a "Did you mean" hint when the value is close to a member, which does not list the members; nothing stored.
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
  "instance": { "label": "us-east-1 PROD", "color": "AMBER" },
  "instance_defaults": { "label": "staging", "color": "AMBER" }
}
```

Both keys have the schema `InstanceIdentityAPI` (`label: string | null`, `color: InstanceColor | null`). `instance_defaults` was added on 2026-11-10 ([IFC-3588](https://opsmill.atlassian.net/browse/IFC-3588)); the example shows a saved label and a deployment default color.

- `instance_defaults`: the deployment defaults from `config.SETTINGS.instance` (see *Settings* below), `null` for a default that is not set.
- `instance`: the identity in effect. Each field is resolved on its own: the value saved on the global `Preference` row if it is not `null`, else the deployment default, else `null`. With no global row, `instance` equals `instance_defaults`.
- When reading the global row raises any exception, the error is logged ("Instance identity unavailable, serving it as unset") and `instance` is `{"label": null, "color": null}`, as before IFC-3588. It does not fall back to the defaults, because a default could name a different stage than the saved value. `instance_defaults` is still served.
- Reading never creates the preference row.

`InfrahubGlobalPreferences` is unchanged by IFC-3588: it returns the saved `instance_label` and `instance_color` only, `null` when not saved, even when the deployment sets a default. Resetting a saved value with an explicit `null` in `InfrahubSetPreferences` makes the default apply again in `/api/config`. Known limitation: While a deployment default is set for a field, the web UI cannot remove that field; it can only replace it with a saved value, because an empty saved value falls back to the default (the precedence the tech owner chose on 2026-11-10).

## Settings `InstanceSettings` (added 2026-11-10, IFC-3588)

| Field | Environment variable | `infrahub.toml` | Type | Default |
|---|---|---|---|---|
| `label` | `INFRAHUB_INSTANCE_LABEL` | `[instance]` `label` | `str \| None` | `None` |
| `color` | `INFRAHUB_INSTANCE_COLOR` | `[instance]` `color` | `InstanceColor \| None` (`RED`, `AMBER`, `GREEN`, `BLUE`, `INDIGO`, `PURPLE`, `GRAY`) | `None` |

Validation, run when the settings load:

- `label` goes through `validate_instance_label(value, field_name="INFRAHUB_INSTANCE_LABEL")`: surrounding whitespace is stripped; an empty or whitespace-only value becomes `None`; a control character (including U+2028 and U+2029) or a bidirectional text control, or more than 32 characters, is rejected with "INFRAHUB_INSTANCE_LABEL cannot contain control characters" or "INFRAHUB_INSTANCE_LABEL cannot be longer than 32 characters". The mutation keeps the field name `instance_label` in its messages.
- `color` is stripped and uppercased; an empty or whitespace-only value becomes `None`; `red` and ` Red ` become `RED`. Any other value is rejected with "INFRAHUB_INSTANCE_COLOR must be one of RED, AMBER, GREEN, BLUE, INDIGO, PURPLE, GRAY".
- The messages name the environment variable also when the value comes from the `[instance]` section of `infrahub.toml`.
- An invalid value stops the process at startup: the configuration loader prints "Configuration not valid, found N error(s)" followed by the field name and the message (for example `color | Value error, INFRAHUB_INSTANCE_COLOR must be one of ...`), and exits with code 1.

`docker-compose.yml` and `development/docker-compose.yml` pass both variables through to the containers. The configuration reference (`docs/docs/reference/configuration.mdx`) lists them in an *Instance* section.
