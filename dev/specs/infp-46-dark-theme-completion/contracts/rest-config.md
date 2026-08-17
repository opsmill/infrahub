# Contract: the dark-theme feature flag on the config payload

**Feature**: [spec.md](../spec.md) | **Covers**: FR-010, FR-011, FR-012, FR-013

The theme feature is gated per deployment. The gate is not a preference — it is a property of the
deployment, needed before a user exists — so it travels on the unauthenticated config payload.

⚠ `schema/openapi.json` and `frontend/app/src/shared/api/rest/types.generated.ts` are generated.
Regenerate with `uv run invoke schema.generate-jsonschema` and `cd frontend/app && pnpm codegen`, and
commit; CI validates them.

## Why this endpoint

`backend/infrahub/api/internal.py` exposes two endpoints with different auth postures:

| Endpoint | Auth | Carries |
|---|---|---|
| `GET /api/config` | **none** | `main`, `logging`, `analytics`, `experimental_features`, `sso`, `ldap`, `installation_type`, `policy` |
| `GET /api/info` | `Depends(get_current_user)` | `deployment_id`, `version` |

The login page must know whether the feature exists before there is a session, and `/api/config`
already carries `experimental_features`. So the flag needs **no new field and no new endpoint** — it
joins a payload the frontend already consumes.

## Settings delta

```diff
 class ExperimentalFeaturesSettings(BaseSettings):
     model_config = SettingsConfigDict(env_prefix="INFRAHUB_EXPERIMENTAL_")
     graphql_enums: bool = False
     value_db_index: bool = Field(default=False, deprecated="…")
+    dark_theme: bool = False
```

A plain `bool` defaulting to `False`, matching `graphql_enums` exactly. No tri-state is needed: unlike
the earlier design there is nothing to distinguish "unset" from "off", because the flag no longer
carries a derived value.

## Deployment configuration

Following the convention both existing flags already use in `development/docker-compose.yml` and the
root `docker-compose.yml`:

```diff
   INFRAHUB_EXPERIMENTAL_GRAPHQL_ENUMS: ${INFRAHUB_EXPERIMENTAL_GRAPHQL_ENUMS:-false}
   INFRAHUB_EXPERIMENTAL_VALUE_DB_INDEX: ${INFRAHUB_EXPERIMENTAL_VALUE_DB_INDEX:-false}
+  INFRAHUB_EXPERIMENTAL_DARK_THEME: ${INFRAHUB_EXPERIMENTAL_DARK_THEME:-true}
```

⚠ The development stack defaults this one to **`true`**, unlike its two neighbours — that single
character is what delivers SC-008 (an engineer gets dark with zero further steps). The env var still
overrides, so an engineer who wants light can set it without editing the file.

⚠ Decide deliberately whether the **root** `docker-compose.yml` also defaults to `true`. It is used
for deployments beyond the dev stack; defaulting it on there widens the blast radius past "the
deployments we run".

## What the flag governs

While dark is alpha the flag does two jobs at once. This is deliberate compression, not conflation —
they separate when the flag is removed.

| Flag | Theme setting offered | Default for a user who has not chosen |
|---|---|---|
| `false` | **No** — the field is absent entirely | light |
| `true` | Yes — light / dark (alpha) / match-system | **dark** |

⚠ With the flag off the field is hidden **entirely**, not reduced to light-only. Offering "light" and
"match system" would leave a hole: a user on a dark operating system selects match-system and reaches
the alpha palette, defeating the flag. A one-option picker is also not a setting.

## Behavioural contract

| Given | When | Then |
|---|---|---|
| Flag `true`, no stored preference | app loads | dark, whatever the operating system says |
| Flag `true`, no stored preference, light OS | app loads | **dark** — the default never consults the system |
| Flag `false`, no stored preference, dark OS | app loads | **light**, and no theme setting is rendered |
| Flag `true`, user chose light | app loads | light — the user's choice beats the default |
| Flag `true`, user chose match-system | OS appearance changes | follows live, because they asked for it |
| Flag flipped `true` → `false`, user had dark stored | app loads | light; **the stored preference is retained** |
| Flag flipped back `false` → `true` | app loads | that user's dark choice is honoured again |
| Any state | anonymous request to `/api/config` | succeeds; no version information disclosed |

## Consumer contract

```text
if (!config.experimental_features.dark_theme) → light; render no theme field
else  choice   = effective.theme.value ?? DARK
      resolved = choice == SYSTEM ? (prefers-color-scheme: dark ? dark : light) : choice
```

`resolved` is mirrored to local storage so the next load's pre-paint script paints correctly from the
first frame.

⚠ The pre-paint script's empty-cache fallback is **light**, never `prefers-color-scheme`. It runs
before the config payload has arrived, so it cannot know whether the flag is on — and guessing from
the operating system would put a dark-OS user into the alpha palette on a deployment where the
feature is switched off entirely.

## What this contract replaced

An earlier revision published a computed `default_theme` derived from the running version's PEP 440
pre-release status. Withdrawn: "pre-release" catches any beta or release candidate, including one a
customer runs in their own environment, which is broader than the intended "the deployments we run".
Following the existing experimental-settings convention targets exactly the intended deployments and
removes the resolver, the version parsing, and the config field. See [research.md](../research.md) §R1.
