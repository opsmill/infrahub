# Rendering dates: always via the preference-aware mechanism

User-facing dates and times must render against the user's **preferences** (`date_format` +
`timezone`), through **one** mechanism — never with an ad-hoc `format(...)` / `toLocaleString(...)`
and never a hardcoded pattern.

## Use one of these

- **Rendering JSX → `<DateDisplay date={…} />`** (`shared/components/display/date-display.tsx`).
  - Default: relative "x ago" for recent dates, a compact date otherwise; the **tooltip** shows the
    user's full preferred datetime + timezone.
  - `variant="datetime"`: render the user's full preferred datetime + timezone inline (use for a
    site that shows a full timestamp).
  - `dateFormat="<date-fns pattern>"`: explicit escape hatch — pins a specific pattern, bypassing the
    preference. Use only when a format genuinely must not follow the user's preference (rare).
- **Need a date *string* in code → `useFormatDate()`** (`shared/context/date-preferences-context.tsx`):
  `const { formatDate } = useFormatDate();` then `formatDate(date, variant?)` with
  `variant ∈ "datetime" (default) | "date" | "relative"`.

## How it's wired (feature-sliced-design safe)

- `DatePreferencesContext` + `useFormatDate` live in **`shared`** and carry **no** dependency on
  `entities/`.
- `DatePreferencesProvider` (`entities/preferences/ui/date-preferences-provider.tsx`) fills the
  context from `useGetEffectivePreferences()`. It is mounted **inside `RequireAuth`** (`app/router.tsx`),
  next to `BranchesProvider`/`SchemaProvider` — never at the app root — because its query is
  authenticated: mounting it above the login page would fire a pre-auth request whose 401 trips
  Apollo's error link and bounces back to `/login`.
- When no provider is mounted, or a preference's `source` is `"DEFAULT"` (nothing set), formatting
  falls back to the **browser locale + zone** (`toLocaleString`) — never a hardcoded pattern. So
  `DateDisplay`/`useFormatDate` are always safe to use, including in tests/stories.
- Timezone rendering uses date-fns v4 + the first-party **`@date-fns/tz`** (`TZDate`). The semantic
  `date_format` key → date-fns pattern mapping is `patternForKey`
  (`entities/preferences/domain/rules/date-format.ts`); the `date` variant derives a date-only
  pattern by stripping the preferred pattern at its first time token.

## Do NOT route through it

Machine/serialized values, not user-facing display: form inputs / date-pickers
(`datetime.field.tsx`, `date-picker.tsx`), `.toISOString()` sent to an API or used as a key/query
param, chart axis ticks, and tests.
