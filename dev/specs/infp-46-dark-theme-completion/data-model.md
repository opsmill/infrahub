# Data Model: Dark Theme Completion

**Feature**: [spec.md](./spec.md) | **Research**: [research.md](./research.md) | **Date**: 2026-08-17

Three entities from the spec, plus the resolution chain that connects them. Nothing here is a new
storage concept: the theme preference is a new field on an existing record, and the deployment
default is computed, never persisted.

## Entities

### Theme

A closed set of appearance choices. Persisted as its member name, like the existing `DateFormat`.

| Value | Meaning |
|---|---|
| `LIGHT` | Always the light palette |
| `DARK` | Always the dark palette. Pre-release (FR-008) |
| `SYSTEM` | Follow the operating system's current appearance |

`SYSTEM` is stored as an explicit choice, not as absence. Absence means "inherit from the next layer
down" and is represented by `null`, exactly as `date_format` and `timezone` already do. Conflating
the two would make "follow my OS" indistinguishable from "I never chose", and an organisation
default could then never be overridden back to system-following.

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

### Deployment default theme

Computed per deployment, never stored. Derived from the running build's PEP 440 pre-release status,
overridable by explicit operator configuration.

```text
deployment_default_theme : LIGHT | DARK | SYSTEM
  = operator override, when configured
  | DARK    when Version(running_version).is_prerelease
  | SYSTEM  otherwise
```

The production default is `SYSTEM`, not a fixed palette: a deployment with no opinion about a
particular user defers to that user's own browser setting. Non-production overrides that to `DARK`
deliberately, because the point is that the team sees dark whatever their operating system says.

It is a *default*, not a value written anywhere: it never touches a stored preference (FR-013), so a
deployment that flips from pre-release to release changes what un-chosen users see and changes
nothing for users who chose.

## Resolution chain

Two distinct stages, deliberately separated. Conflating them is the mistake that makes GraphiQL and
the application disagree (see [research.md](./research.md) §R3).

### Stage 1 — resolve the stored choice

Server-side, identical in shape to the existing preferences:

```text
effective.theme.value   = user.theme  ?? global.theme  ?? null
effective.theme.source  = USER        |  GLOBAL        |  DEFAULT
```

`source` reports which layer answered, so the interface can say "Your preference" versus "From the
organisation default" versus falling through — the convention `preference-fields.tsx` already
implements.

When the chain yields `null` (source `DEFAULT`), the client substitutes the deployment default from
the config payload.

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
| choice | the stored choice, or the deployment default | the effective preference resolves |
| resolved | `light` or `dark` | stage 2 completes |

Read synchronously by the inline classification script before first paint. It is a cache, never a
source of truth: the account-backed preference always wins on arrival, and a cleared mirror costs one
corrected repaint rather than a wrong theme.

⚠ On a cold start the mirror is empty, and the fallback is the browser's own appearance — the same
answer the production deployment default gives. Cache-hit and cache-miss therefore agree, so a
first-ever visit is correct rather than merely tolerable. The one case that still corrects after the
config payload arrives is a **non-production** deployment on a light system: the script paints light
from the system, then flips to dark. Accepted — it affects the team's own builds only.

Cross-tab synchronisation is out of scope; a second tab picks up a change on its next load.

## Relationships

```text
Account ──owns──▶ Preference(owner_id = account id)   ─┐
                                                       ├─▶ effective choice ─▶ resolved ─▶ consumers
Organisation ───▶ Preference(owner_id = GLOBAL)       ─┤                                    (document class,
                                                       │                                     GraphiQL,
Deployment ─────▶ default theme (computed)            ─┘                                     Mermaid,
                                                                                             visualizer)
Operating system ────────────────────────────────────────▶ (consumed by stage 2 only)
```

## Validation rules

- `theme` accepts only `Theme` members; unknown values are rejected at construction, including on
  load from the database — the behaviour `date_format` already relies on by being enum-typed.
- Writing `null` clears the override at that layer and re-exposes the layer below; it is not an error
  and is how a user returns to "Automatic (inherited)".
- Writing the global layer requires the same permission as the existing global preference writes; no
  new permission is introduced.
- The deployment default may be `SYSTEM`, and on production it is. The server cannot observe an
  operating system's appearance, but it does not need to: `SYSTEM` is a *deferral*, and stage 2
  resolves it on the client — including inside the pre-paint script, which can read the browser's
  appearance synchronously. A `SYSTEM` default therefore leaves the client with a complete answer on
  a cold start rather than a gap.
