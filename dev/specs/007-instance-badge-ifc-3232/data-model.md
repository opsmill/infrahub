# Data model: instance label and color

## `Preference` StandardNode (existing, `backend/infrahub/core/preferences/models.py`)

| Field | Type | New | Rule |
|---|---|---|---|
| `owner_id` | `str` | no | `"__global__"` for the instance-wide row |
| `date_format` | `Optional[DateFormat]` | no | unchanged |
| `timezone` | `Optional[str]` | no | unchanged |
| `instance_label` | `Optional[str]` | yes | trimmed; `None` when unset; at most 32 characters; no control character; not `NULL` |
| `instance_color` | `Optional[InstanceColor]` | yes | one of the presets or `None` |

The two new fields are meaningful on the global row only. A per-user row never carries them: the mutation rejects them for `scope: USER`, and the user and effective GraphQL types do not expose them. `EffectivePreferences` is unchanged.

## `InstanceColor` enum (`backend/infrahub/instance_identity.py`)

`InstanceColor(InfrahubStringEnum)` with name == value: `RED`, `AMBER`, `GREEN`, `BLUE`, `INDIGO`, `PURPLE`, `GRAY`. Stored as the string value. Renaming a member later needs a data migration.

`INSTANCE_LABEL_MAX_LENGTH = 32` in the same module.

The enum, the constant and the label validator were first written in `backend/infrahub/core/preferences/constants.py` and `validation.py`, and moved to `backend/infrahub/instance_identity.py` on 2026-11-10 (IFC-3588) so that `backend/infrahub/config.py` can import them (see the plan).

## Validation (`backend/infrahub/instance_identity.py`)

`validate_instance_label(value: str | None, field_name: str = "instance_label") -> str | None`: strips surrounding whitespace; an empty result becomes `None`; a control character (Unicode category Cc, the line and paragraph separators U+2028 and U+2029 in categories Zl and Zp, or a bidirectional text control) a length over 32, or a value equal to `NULL` (the text the preference node stores for an unset value) raises `ValidationError` whose message starts with `field_name` and names the rule. The mutation uses the default; `InstanceSettings` passes `"INFRAHUB_INSTANCE_LABEL"`. It runs on the write path and when the deployment settings load, never on the model, so a stored value never breaks a read.

The color needs no validator on the write path: the GraphQL enum rejects an unknown member with the graphql-core message `Variable '$instance_color' got invalid value '<x>'; Value '<x>' does not exist in 'InstanceColor' enum.`, followed by a "Did you mean" hint when the value is close to a member, which does not list the allowed values (the schema does). The deployment setting validates the color in `InstanceSettings` with its own message (see below).

## `InstanceSettings` (`backend/infrahub/config.py`, added 2026-11-10, IFC-3588)

Deployment defaults, read once when the settings load. They are not stored in the database and never written to the `Preference` row.

| Field | Type | Source | Rule |
|---|---|---|---|
| `label` | `str \| None` | `INFRAHUB_INSTANCE_LABEL` or `[instance]` `label` in `infrahub.toml` | `validate_instance_label` with `field_name="INFRAHUB_INSTANCE_LABEL"`; empty or whitespace-only → `None`; an invalid value stops startup |
| `color` | `InstanceColor \| None` | `INFRAHUB_INSTANCE_COLOR` or `[instance]` `color` in `infrahub.toml` | stripped and uppercased; empty or whitespace-only → `None`; otherwise a member name in any letter case; an unknown value stops startup with "INFRAHUB_INSTANCE_COLOR must be one of RED, AMBER, GREEN, BLUE, INDIGO, PURPLE, GRAY" |

`Settings.instance` is built with `Field(default_factory=InstanceSettings)`, so an invalid value is reported when the settings load rather than when `config.py` is imported. `config.SETTINGS.instance` returns it.

## Resolution of the identity in effect (`backend/infrahub/api/internal.py`)

`InstanceIdentityResolver.resolve` resolves each field of `/api/config` `instance` on its own:

1. The field of the global `Preference` row, when the row exists and the field is not `None`.
2. Else the field of `InstanceSettings`.
3. Else `None`.

With no global row, both fields come from `InstanceSettings`. When reading the row raises any exception (logged), both fields are `None`: a default could name a different stage than the saved value it stands in for. `instance_defaults` always carries `InstanceSettings` unchanged. `InfrahubGlobalPreferences` and the `Preference` row are not affected: they hold saved values only.

Known limitation: While a deployment default is set for a field, the web UI cannot remove that field; it can only replace it with a saved value, because an empty saved value falls back to the default (the precedence the tech owner chose on 2026-11-10).

## Frontend presets (`frontend/app/src/entities/preferences/domain/rules/instance-color.ts`)

| Enum value | Badge variant | Bar class | Tab icon color | Label |
|---|---|---|---|---|
| `RED` | `red` | `bg-danger` | `#be123c` | Red |
| `AMBER` | `warning` | `bg-warning-strong` | `#f59e0b` | Amber |
| `GREEN` | `green` | `bg-success` | `#15803d` | Green |
| `BLUE` | `blue` | `bg-info` | `#0369a1` | Blue |
| `INDIGO` | `indigo` (new) | `bg-active` | `#4338ca` | Indigo |
| `PURPLE` | `purple` | `bg-purple-600 dark:bg-purple-400` | `#9333ea` | Purple |
| `GRAY` | `gray` | `bg-foreground-muted` | `#57534e` | Gray |
| unset | `gray` (badge only when a label exists) | none | none (standard icon) | — |

The tab icon color (`faviconColor`, added 2026-11-10) is a hex value rather than a theme token because the browser renders the tab icon outside the page, where the theme tokens do not apply. `instanceFaviconColor(color)` returns it, or `null` for an unset or unknown color.
