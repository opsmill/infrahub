# Data model: instance label and color

## `Preference` StandardNode (existing, `backend/infrahub/core/preferences/models.py`)

| Field | Type | New | Rule |
|---|---|---|---|
| `owner_id` | `str` | no | `"__global__"` for the instance-wide row |
| `date_format` | `Optional[DateFormat]` | no | unchanged |
| `timezone` | `Optional[str]` | no | unchanged |
| `instance_label` | `Optional[str]` | yes | trimmed; `None` when unset; at most 32 characters; no control character |
| `instance_color` | `Optional[InstanceColor]` | yes | one of the presets or `None` |

The two new fields are meaningful on the global row only. A per-user row never carries them: the mutation rejects them for `scope: USER`, and the user and effective GraphQL types do not expose them. `EffectivePreferences` is unchanged.

## `InstanceColor` enum (`backend/infrahub/core/preferences/constants.py`)

`InstanceColor(InfrahubStringEnum)` with name == value: `RED`, `AMBER`, `GREEN`, `BLUE`, `INDIGO`, `PURPLE`, `GRAY`. Stored as the string value. Renaming a member later needs a data migration.

`INSTANCE_LABEL_MAX_LENGTH = 32` in the same module.

## Validation (`backend/infrahub/core/preferences/validation.py`)

`validate_instance_label(value: str | None) -> str | None`: strips surrounding whitespace; an empty result becomes `None`; a control character (Unicode category Cc or a bidirectional text control) or a length over 32 raises `ValidationError` whose message names the rule. It runs on the write path only, never on the model, so a stored value never breaks a read.

The color needs no validator: the GraphQL enum rejects unknown members with a message listing the allowed values, and Pydantic does the same on the REST model.

## Frontend presets (`frontend/app/src/entities/preferences/domain/rules/instance-color.ts`)

| Enum value | Badge variant | Bar class | Label |
|---|---|---|---|
| `RED` | `red` | `bg-danger` | Red |
| `AMBER` | `warning` | `bg-warning-strong` | Amber |
| `GREEN` | `green` | `bg-success` | Green |
| `BLUE` | `blue` | `bg-info` | Blue |
| `INDIGO` | `indigo` (new) | `bg-active` | Indigo |
| `PURPLE` | `purple` | `bg-purple-600 dark:bg-purple-400` | Purple |
| `GRAY` | `gray` | `bg-foreground-muted` | Gray |
| unset | `gray` (badge only when a label exists) | none | — |
