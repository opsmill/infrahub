# 01 — System inventory: account settings

Paths are relative to `frontend/app/src` unless they start with `frontend/`.

## Covered

**Page frame**
- `Content.Card` + `Content.CardTitle` (`shared/components/layout/content.tsx`). This is
  the frame of every top-level page (`/profile`, `/global-preferences`, role management,
  schema). `CardTitle` takes `title`, `description`, `end`, `badgeContent`.
- `DetailsLayout` with `.Main`/`.Aside` (`shared/components/layout/details-layout.tsx`).
  The Profile tab already uses it, and it stays (content unchanged, per the brief).
- `Row`/`Col` (`shared/components/container.tsx`), the house rule instead of bare flex divs.
- `Card`, `CardHeader`, `CardContent`, `ScrollArea`, `ResizablePanelGroup`/`Panel`/`Handle`,
  `Sheet`, `Modal`, `Button`/`LinkButton`, `Menu`, `Spinner`, `Tooltip`, all from
  `@infrahub/ui`.

**Navigation**
- `LinkTab` (`shared/components/ui/link.tsx`) in `<nav aria-label="Tabs">`: URL-driven
  horizontal tabs (today's `/profile`). Role management adds an icon and a count `Badge`
  per tab.
- `LinkToggleButtonGroup` (`shared/components/buttons/link-toggle-button.tsx`): a segmented
  route toggle (schema page).
- `menuNavigationItemStyle` (`entities/navigation/ui/sidebar/styles.ts`): the app sidebar's
  nav item style (`px-2.5 py-2 rounded-lg hover:bg-highlight`). It can be reused for a
  vertical settings nav.
- `Tabs`/`TabsList`/`TabsTrigger`/`TabsContent` (`shared/components/ui/tabs.tsx`): Radix,
  `underline` | `field` variants, for in-page (non-URL) tabs.

**Section content (reused as is)**
- Profile: `ObjectDetailsCard`, `ObjectProfilesGroupsCard`, `ObjectActivitiesCard`.
- Preferences: `UserPreferencesCard` → `PreferencesForm` (date format, timezone; dirty-gated
  Save, toast).
- Tokens: `AccountTokenCreateAction` (Sheet form → non-dismissable "Token created" modal
  with `CopyToClipboard`), `AccountTokenItem` + `ExpirationDate`,
  `AccountTokenDeleteAction`.
- Password: `PasswordInputField` inside `Form`/`FormSubmit`.
- Global preferences: `GlobalPreferencesEditor` (Card, max-w-3xl, "Global date and time").

**States and small pieces**
- `ErrorScreen`, `NoDataFound`, `UnauthorizedScreen` (`shared/components/errors/`).
- `LoadingIndicator`, `Skeleton`.
- `Avatar`, `Badge`, `Separator`, `RadioGroup`/`Radio` (`shared/components/aria/`).

**Permission:** `useHasGlobalPermission(MANAGE_GLOBAL_PREFERENCES)` and
`RequireGlobalPermission`, as `account-menu.tsx` and `pages/global-preferences.tsx` use
them.

**Theme:** `useTheme()` → `{ theme, setTheme }`, `"system" | "light" | "dark"`
(`entities/config/ui/theme-provider.tsx`).

## Close

- **Vertical settings nav.** There's no component, but `menuNavigationItemStyle` and
  `LinkTab`'s `useMatch` behaviour cover the parts. Missing: an active-state treatment for a
  vertical list, and group headings ("Personal" / "Administration"). Composing it from
  `Link` + that style is enough for a prototype; whether it becomes a shared primitive is a
  phase 5 question.
- **Empty state.** `NoDataFound` is a single line of text; `ObjectTableEmpty` is tied to a
  schema. Neither takes a title, an explanation and an action, which is what the
  empty-tokens state needs (SC-003).
- **Inline callout.** `Alert` exists but is shaped for toasts. There's no in-page
  Callout/Banner for "password managed externally" or "token list failed to load, retry".
- **Theme picker on a settings page.** The only picker is `ThemeMenuItem`, a submenu in the
  account menu. Showing the existing `theme` value in Preferences with `RadioGroup` surfaces
  a setting that already exists; it doesn't add one (in scope per the brief, needed for
  SC-004). The "alpha" tag on Dark carries over.

## Missing

- **A settings-shell layout.** No page in the app has a vertical settings side-nav; the
  nearest is IPAM's resizable tree panel. Building it would mean a two-column layout inside
  `Content.Card` (nav ~200px, content fills), built from `Row`/`Col` and `ScrollArea`. No new
  primitive yet.
- **A generic empty state with an action** (title, explanation, primary action).
  `design-system.md` says a new generic primitive belongs in `@infrahub/ui` with a Storybook
  story. That is a real gap this design creates, not something the prototype should
  quietly fill.
- **A prototype route.** None exists. See below.

## Where the prototype mounts

Every direction changes **only the content area**: the settings shell sits inside the
app's existing sidebar and header. Merging the "Global preferences" menu item into
"Account settings" is a one-line menu change, recorded in the brief, and not something any
revision needs to render.

So the prototype mounts **inside the app layout**: a child of `path: "/"`
(`pages/app-layout.tsx`) at **`/_proto/account-settings`**. The panel takes `frame`, so
the real `AppSidebar` and `AppHeader` stay on screen. The route registration carries a
`PROTOTYPE design-jam account-settings` marker.

Data: prototype sections use worst-case **mock** data (many tokens with long names, no
expiry, expired, zero tokens, a load error, an externally-managed account, no admin
permission, a long display label and no description) behind panel knobs, not live
queries. A prototype that only shows the logged-in admin's tidy account can't show any
of the states SC-003 is about.
