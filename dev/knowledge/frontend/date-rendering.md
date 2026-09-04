# Rendering dates: always via the preference-aware mechanism

User-facing dates and times must render against the user's **preferences** (`date_format` +
`timezone`), through **one** mechanism — never with an ad-hoc `format(...)` / `toLocaleString(...)`
and never a hardcoded pattern.

## Use one of these

- **Rendering JSX → `<DateDisplay date={…} />`** (`shared/components/display/date-display.tsx`).
  - Default: relative ("x ago" / "in x") within a week either side of now, a compact date beyond;
    the **tooltip** shows the user's full preferred datetime, rendered in their preferred timezone.
  - `fullTimestamp`: render the user's full preferred datetime inline, in their preferred
    timezone (use for a site that shows a full timestamp).
  - The value renders *in* the preferred timezone, but an offset/label only shows when the chosen
    `date_format` preset includes one (e.g. `ISO_8601`); other presets render a bare datetime.
  - There is deliberately no per-call-site pattern override: every `DateDisplay` follows the
    user's preference so dates look the same everywhere.
- **Need a date *string* in code → `useFormatDate()`** (`shared/context/date-preferences-context.tsx`):
  `const { formatDate } = useFormatDate();` then `formatDate(date, variant?)` with
  `variant ∈ "datetime" (default) | "date" | "relative"`.
- **Previewing preferences that are not the viewer's active ones → `formatWithPreferences()`** (same
  module, backs the hook): the pure function, for the rare caller that must render against an
  explicit `{ pattern, timezone }` pair. Only the preferences forms need it, and only for their
  "Example:" line, which renders the values the form currently holds — including unsaved edits, and
  the inherited layer for a field left empty — so it shows what the timestamps become on save. The
  source tooltip beside it renders **no** sample: it names the format by its label, which keeps it
  independent of the form's timezone field. Anything rendering against the viewer's active
  preferences uses the hook, never this. An editor of the org-wide default must not reach for the
  hook — that would preview everyone's default in the admin's own zone.

## How it's wired (feature-sliced-design safe)

- `DatePreferencesContext` + `useFormatDate` live in **`shared`** and carry **no** dependency on
  `entities/`.
- `DatePreferencesProvider` (`entities/preferences/ui/date-preferences-provider.tsx`) fills the
  context from `useGetEffectivePreferences()`, but **only once the user is authenticated** — it
  returns its children unchanged when logged out. The query needs auth, yet the app also renders for
  logged-out users (`allow_anonymous_access`), so an ungated fetch would 401 and the transport's
  error routing would bounce them to `/login`. Gating by *mount* (not react-query `enabled`) keeps the query hook
  auth-agnostic. `RequireAuth` is **not** a sufficient gate here — it renders for anonymous users too.
- When no provider is mounted, or a preference's `source` is `"DEFAULT"` (nothing set), formatting
  falls back to the **browser locale + zone** (`toLocaleString`) — never a hardcoded pattern. So
  `DateDisplay`/`useFormatDate` are always safe to use, including in tests/stories.
- Timezone rendering uses date-fns v4 + the first-party **`@date-fns/tz`** (`TZDate`). The semantic
  `date_format` key → date-fns pattern mapping is `dateFormatPattern`
  (`entities/preferences/domain/rules/date-format.ts`); the `date` variant derives a date-only
  pattern by stripping the preferred pattern at its first time token.

## Do NOT route through it

Machine/serialized values, not user-facing display: form inputs / date-pickers
(`datetime.field.tsx`, `date-picker.tsx`), `.toISOString()` sent to an API or used as a key/query
param, chart axis ticks, and tests.
