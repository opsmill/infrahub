# 00 — Brief: account settings

**Seed (user's words):** "lets try to find better way to display all the pages for the profile
and account settings"

## Passes

- Product framing (`emil-product-thinking`) **skipped at the user's request**. The skill is
  user-invocation only; the user chose to skip rather than run it.
- `grilling-ideas` ran, 8 questions, 2026-10-01. Its idea brief is captured below.

## Done looks like

Account settings is one place where every section the user can access is named in visible
navigation, one click from any other section, each with its own URL, and no section ends in
a dead end.

## Today

`/profile` = `Content.Card` with avatar header, then three horizontal `LinkTab`s:

- **Profile:** the generic object detail layout for `CoreGenericAccount` (details card and
  `UserPreferencesCard` in main, profiles/groups and activities in aside).
- **Tokens:** a page-level `h1` and description, a create action, and a `Card` list. An empty
  list renders an empty card; an error renders raw text.
- **Password:** a lone centred `max-w-md` card, or a dead-end "managed externally" card.

`/global-preferences` is a separate admin-only page in the account menu, gated by
`canManageGlobalPreferences`.

## Who hits this, and what they were doing before

1. **Automation engineer (primary).** Writing a script, pipeline or `infrahubctl` config,
   needs an API token: account menu → Account settings → Tokens. Comes back when a token
   expires or leaks.
2. **Any user, occasionally.** Wants to change password, date format/timezone, or theme
   (System option landed in #10788). Today preferences sit under the account details card,
   so "where's the theme?" has no obvious answer.

**Content stays as today.** Details, groups/profiles and activity are kept; this design
changes how the pages are arranged and reached.

## Journeys

- **P1 — Reach any setting directly.** *Given* a logged-in user on any page, *when* they
  open Account settings, *then* every section is named in visible navigation, and each has
  its own deep-linkable URL.
- **P2 — Each section fits its job.** Tokens has a real list with empty and error states;
  Password has a layout that doesn't float, and its externally-managed state says what to do
  instead. **Prototypes show P2 on and off** so the two can be compared.

## Functional requirements (draft)

- **FR-001:** Users MUST be able to reach preferences from visible navigation in one click.
  Whether Preferences becomes its **own section or stays inside Profile is explored in the
  prototypes**, not decided here.
- **FR-002:** Global preferences MUST appear as a section of the same shell, visible only
  with `canManageGlobalPreferences`. Its URL is not decided here.
- **FR-003:** Every section MUST have a URL that opens straight onto it.

## Success criteria

- **SC-001:** From the landing view, every section the user can access is named on screen
  without scrolling or opening anything, at 1280×800.
- **SC-002:** Each section is reachable in one click from any other, via its own URL.
- **SC-003:** No section has a dead end: empty tokens, a token load error and an
  externally-managed password each say what is happening and what to do next.
- **SC-004:** In review, people asked to "create a token" and "switch to dark theme" find
  the control unaided in the chosen direction: zero pinned "couldn't find" notes.

## Riskiest assumption

The problem is the **layout**, not that people can't find the page. If users never reach
Account settings (they look for tokens in admin, the docs or `infrahubctl`), no shell design
fixes it. The prototype keeps today's account-menu entry point, and any "I'd never have
found this page" feedback is recorded as a finding, not argued away.

## Out of scope

- New settings content: sessions, SSO/linked identities, notifications, token
  scopes/permissions.
- Backend/GraphQL changes, e.g. token "last used" / "created at" fields that the API doesn't
  return today. The prototype shows only fields that exist.
- Entry points to the page from elsewhere in the app.
- `/global-preferences` URL changes or redirects.
- Admins managing other users' accounts.
- Redesigning the global preferences editor itself; it is placed in the shell as it is.

## Where it's used

**Desk only** (user, 2026-10-01). `emil-mobile-native` is skipped. Phase 4 still checks for
no sideways scroll at phone width.

## Governance

No AGENTS.md "Ask first" gate crossed (no DB, GraphQL, dependency, CI/CD or auth change;
reuses existing queries and the existing permission check). Constitution VII (Simplicity)
applies: build from existing components.
