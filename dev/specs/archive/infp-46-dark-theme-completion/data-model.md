# Data Model: Dark Theme Completion

**Feature**: [spec.md](./spec.md) | **Research**: [research.md](./research.md) | **Date**: 2026-08-17

Three entities from the spec, plus the resolution chain that connects them. Nothing here is a new
storage concept: the theme preference is a new field on an existing record, and the feature flag is
read from configuration, never persisted.

## Entities

### Theme

A closed set of appearance choices. Persisted as its member name, like the existing `DateFormat`.

| Value | Meaning |
|---|---|
| `LIGHT` | Always the light palette |
| `DARK` | Always the dark palette. Pre-release (FR-008) |
| `SYSTEM` | Follow the operating system's current appearance |

`SYSTEM` is stored as an explicit choice, not as absence. Absence means "inherit" and is represented
by `null`, exactly as `date_format` and `timezone` already do. Conflating the two would make "follow
my OS" indistinguishable from "I never chose", so a user could never return to system-following after
setting anything else.

### Theme preference (a field, not a record)

`theme` joins the existing `Preference` record rather than introducing storage of its own.

```text
Preference (StandardNode)
  owner_id     : str                      # account id, or GLOBAL_OWNER_ID sentinel
  date_format  : Optional[DateFormat]     # existing
  timezone     : Optional[str]            # existing
  theme        : Optional[Theme]          # NEW — null means "not set at this layer"
```

Constraints inherited from the existing record, both load-bearing:

- **`Optional[Theme]`, never `Theme | None`.** `StandardNode.guess_field_type` requires the former;
  this is documented in `models.py` and is not lifted by Python 3.14.
- **One row per owner**, with user rows keyed by account id and a single global row keyed by the
  `GLOBAL_OWNER_ID` sentinel. Writes serialise per owner through `PREFERENCE_LOCK_NAMESPACE`.
- **Reads never create a row.** A missing row is "nothing set at this layer".

Adding a nullable field to a `StandardNode` is additive: rows written before this change have no
`theme` property and read back as `None`, which is already a valid, meaningful state. No data
migration is expected — see the governance flag in [research.md](./research.md) §R5.

### Theme feature flag

A per-deployment boolean, read from configuration, never stored against a user. It is not derived
from anything — the deployment states it.

```text
dark_theme : bool   = INFRAHUB_EXPERIMENTAL_DARK_THEME, default false
```

While dark is alpha it governs two things at once:

| `dark_theme` | Theme setting offered | Default for a user who has not chosen |
|---|---|---|
| `false` | none — the field is absent | `LIGHT` |
| `true` | `LIGHT` / `DARK` (alpha) / `SYSTEM` | `DARK` |

Both defaults are concrete palettes, never `SYSTEM`, and both directions are deliberate:

- **Flag off gives `LIGHT`, not `SYSTEM`.** Dark is alpha, so it is reached only by a user's own
  choice. Deferring to the operating system would put dark-OS users into it by inference — and on a
  deployment where the feature is switched off entirely, there is no choice to infer from.
- **Flag on gives `DARK`, not `SYSTEM`.** Following the system would leave every engineer on a light
  machine out of the dogfooding, which is the flag's whole point.

`SYSTEM` remains available to users as an explicit choice wherever the flag is on — it is simply
never a default.

The two jobs separate when the flag is removed: the production default then becomes its own decision
rather than a consequence of the gate.

It is a *default*, not a value written anywhere: it never touches a stored preference (FR-013), so
flipping the flag changes what un-chosen users see and changes nothing for users who chose.

## Resolution chain

Two distinct stages, deliberately separated. Conflating them is the mistake that makes GraphiQL and
the application disagree (see [research.md](./research.md) §R3).

### Stage 1 — resolve the stored choice

Server-side, identical in shape to the existing preferences:

```text
effective.theme.value   = user.theme  ?? global.theme  ?? null
effective.theme.source  = USER        |  GLOBAL        |  DEFAULT
```

The chain is the existing one, unchanged — but **theme is exposed at the user scope only**, so no
interface writes the global layer and `global.theme` is always `null` in practice. The chain
therefore reduces to `user.theme ?? null`. Nothing needs removing from the backend to achieve this:
the mutation's `scope` argument is shared across fields, so the global layer simply has no writer.
When an organisation-wide default is added later, the chain already supports it.

`source` reports which layer answered, so the interface can say "Your preference" versus falling
through to a default — the convention `preference-fields.tsx` already implements.

When the chain yields `null` (source `DEFAULT`), the client substitutes the flag's default: `DARK`
where the flag is on, `LIGHT` where it is off.

### Stage 2 — resolve to a concrete palette

Client-side, because only the client knows the operating system's appearance:

```text
resolved : LIGHT | DARK
  = LIGHT                                  when choice is LIGHT
  | DARK                                   when choice is DARK
  | (prefers-color-scheme: dark) ? DARK
                                 : LIGHT   when choice is SYSTEM
```

`resolved` is a strict two-value output. Every consumer — the document class, GraphiQL's
`forcedTheme`, Mermaid's `mermaidConfig.theme`, the schema visualizer — takes `resolved`, never the
raw choice. That is what guarantees they cannot drift from the application or from each other.

Stage 2 re-runs when the operating system's appearance changes while the page is open (FR-007), which
is why it lives in the client and not in the resolution the server returns.

## Client-side mirror

A `localStorage` mirror of the resolution, existing solely to make the first paint correct (FR-006).

| Key | Holds | Written when |
|---|---|---|
| choice | the stored choice, or the flag's default | the effective preference resolves |
| resolved | `light` or `dark` | stage 2 completes |

Read synchronously by the inline classification script before first paint. It is a cache, never a
source of truth: the account-backed preference always wins on arrival, and a cleared mirror costs one
corrected repaint rather than a wrong theme.

⚠ On a cold start the mirror is empty and the fallback is **light** — not the browser's appearance.
The script runs before the config payload arrives, so it cannot know whether the flag is even on;
guessing from the operating system would put a dark-OS user into the alpha palette on a deployment
where the feature is switched off entirely. Where the flag is off, light is also the final answer, so
a first-ever visit is correct; where it is on, that visit paints light and corrects to dark once the
config payload lands. That single frame is accepted — it affects flag-enabled deployments only.

Cross-tab synchronisation is out of scope; a second tab picks up a change on its next load.

## Relationships

```text
Account ──owns──▶ Preference(owner_id = account id).theme  ─┐
                                                            ├─▶ effective choice ─▶ resolved ─▶ consumers
Deployment ─────▶ dark_theme flag ─▶ default (DARK|LIGHT)  ─┘                                 (document class,
                                                                                              GraphiQL,
Operating system ─────────────────▶ (stage 2 only, and only for an explicit SYSTEM choice)     Mermaid,
                                                                                              visualizer)
```

No organisation edge: the global `Preference` row exists for `date_format` and `timezone`, but
nothing writes `theme` into it in this version.

## Validation rules

- `theme` accepts only `Theme` members; unknown values are rejected at construction, including on
  load from the database — the behaviour `date_format` already relies on by being enum-typed.
- Writing `null` clears the override at that layer and re-exposes the layer below; it is not an error
  and is how a user returns to "Automatic (inherited)".
- Writing the global layer requires the same permission as the existing global preference writes; no
  new permission is introduced.
- The flag's default is always concrete (`LIGHT` or `DARK`) and never `SYSTEM`. This is a policy
  constraint, not a technical one — stage 2 could resolve a `SYSTEM` default perfectly well. It is
  excluded because a defaulted user must never reach the alpha palette by inference, and because a
  system-following default would defeat the dogfooding.
- Turning the flag off MUST NOT delete a stored `theme`. The value is ignored while unreachable and
  honoured again if the flag returns; a configuration change must never destroy user data.
