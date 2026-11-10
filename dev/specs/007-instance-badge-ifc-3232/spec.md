# Feature Specification: Instance label and color as global settings

**Feature Branch**: `ple-instance-badge-ifc-3232` (spec directory `007-instance-badge-ifc-3232`)

**Created**: 2026-11-04

**Updated**: 2026-11-10, scope extended with [IFC-3588](https://opsmill.atlassian.net/browse/IFC-3588) (deployment defaults and the colored tab icon), see the clarification session of 2026-11-10

**Status**: Draft

**Input**: User description: "Instance label and color as new global settings (IFC-3232, product card INFP-538). An administrator with the manage_global_preferences permission sets an instance label (free text, max 32 chars, trimmed, empty = reset) and an instance color (preset: red, amber, green, blue, indigo, purple, gray) on the Global preferences page; both are stored with the global settings and take effect without a restart. Every visitor, including on the login page, views a badge with the label in the header and a thin full-width colored bar at the top of the page, and the browser tab title becomes `<label> · <page title>`. Fields are independent. Reset restores "Infrahub" and no badge or bar. Out of scope: favicon and login logo upload."

**Sources**: [IFC-3232](https://opsmill.atlassian.net/browse/IFC-3232) (mirrored from [opsmill/infrahub#10690](https://github.com/opsmill/infrahub/issues/10690)), product card [INFP-538](https://opsmill.atlassian.net/browse/INFP-538), decisions taken with the tech owner on 2026-11-04. Extension: [IFC-3588](https://opsmill.atlassian.net/browse/IFC-3588) and decisions taken with the tech owner on 2026-11-10. The Input line above is kept as written on 2026-11-04; its favicon exclusion was narrowed on 2026-11-10 (see Clarifications).

## Problem

Teams run several Infrahub instances: one per stage (development, QA, production) or one per region. Their users open several of them in one browser, and every tab reads "Infrahub" with the same look. Nothing in the web UI says which instance a tab shows, so users check the URL before every change, and a change meant for QA can land in production. Three customers asked for a way to tell instances apart, in particular during a schema upgrade and when they move from one instance to another.

## Clarifications

### Session 2026-11-04

- Q: What does the login page show when a label and a color are set? → A: The thin colored bar at the top and the label badge near the Infrahub logo on the login card.
- Q: Where does the badge sit in the top header? → A: On the right of the header, next to the task status and repository sync status indicators (tech owner, 2026-11-05, after viewing the design jam mockups).

### Session 2026-11-10

Scope extension [IFC-3588](https://opsmill.atlassian.net/browse/IFC-3588), shipped in the same pull request as IFC-3232.

- Q: Can the deployment configuration set the label and the color? → A: Yes. Two environment variables, `INFRAHUB_INSTANCE_LABEL` and `INFRAHUB_INSTANCE_COLOR`, or the `[instance]` section of `infrahub.toml`, set a default label and a default color for the instance.
- Q: When the deployment sets a default, can an administrator still change the value in the web UI? → A: Yes. The tech owner chose that a value saved in the web UI overrides the deployment default, rather than locking the fields. Resetting the saved value applies the default again.
- Q: Does the browser tab icon change with the instance color? → A: Yes. The tech owner asked for the colored tab icon after the original scope was written: the outline variant of the Infrahub mark, recolored to the preset color. Only favicon upload and login logo upload stay out of scope.
- Correction (2026-11-10): FR-007 and the edge case on an unknown color said the error lists the allowed values. The GraphQL enum rejects an unknown color with `Value '<x>' does not exist in 'InstanceColor' enum.`, which does not list them; the wording now matches. User Story 5 scenarios 6 and 7 said the startup message starts with the variable name. The configuration loader prints `<field> | Value error, <message>`, and the message after "Value error, " starts with the variable name; the wording now matches.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tell instances apart on every page (Priority: P1)

A user who works in several Infrahub instances opens one of them. On every page, including the login page, they view a badge with the instance label in the top header and a thin colored bar across the top of the page. The color is the one the administrator chose for this instance, so a user who has learned "red is production" knows at a glance where they are before they change data.

**Why this priority**: This is the customer need itself. Without the indicator on the page, the setting has no value.

**Independent Test**: With a label and a color stored for the instance, open any page as any user (administrator, read-only user, anonymous visitor on the login page) and view the badge text and the bar color. Reload the page and view the same.

**Acceptance Scenarios**:

1. **Given** the instance label is "us-east-1 PROD" and the color is red, **When** a read-only user opens the branches page, **Then** the top header shows a badge reading "us-east-1 PROD" in the red style and a thin red bar spans the full width at the top of the page.
2. **Given** the same settings, **When** an anonymous visitor opens the login page, **Then** the login page shows the thin red bar at the top and the badge with the label near the Infrahub logo on the login card, before the visitor enters credentials.
3. **Given** the same settings, **When** the user reloads the page or navigates to another page, **Then** the badge and the bar are still shown.
4. **Given** no label and no color are stored and the deployment sets no default, **When** any user opens any page, **Then** no badge and no bar are rendered, and the layout is identical to today.
5. **Given** a color is stored but no label, and the deployment sets no default label, **When** a user opens a page, **Then** only the bar is shown, in that color.
6. **Given** a label is stored but no color, and the deployment sets no default color, **When** a user opens a page, **Then** only the badge is shown, in the neutral gray style, and no bar.
7. **Given** a label longer than the badge can display at the header width, **When** a user hovers the badge, **Then** the badge shows the label truncated with an ellipsis and a tooltip shows the full label.

---

### User Story 2 - Tell browser tabs apart (Priority: P1)

A user has tabs of several instances open. Each tab title starts with the label of its instance, followed by the page title, so the tabs can be told apart in the tab bar and in the browser history.

**Why this priority**: The tab title is the only indicator visible when the page itself is not in front of the user, and the GitHub request and the product card both list it as a must-have.

**Independent Test**: With a label stored, open a page and read the document title; clear the label and read it again.

**Acceptance Scenarios**:

1. **Given** the label is "QA", **When** a user opens the schema page, **Then** the tab title is "QA · Schema".
2. **Given** the label is "QA", **When** a user opens a page that has no page title of its own, **Then** the tab title is "QA · Infrahub".
3. **Given** no label is stored and the deployment sets no default label, **When** a user opens the schema page, **Then** the tab title is "Schema", exactly as today.
4. **Given** the label is "QA" and the user navigates from the schema page to a page without its own title, **Then** the tab title changes from "QA · Schema" to "QA · Infrahub", never to a title without the label.
5. **Given** the color is red, **When** a user opens any page, **Then** the browser tab icon shows the Infrahub mark in red (added 2026-11-10).
6. **Given** no color is stored and the deployment sets no default color, **When** a user opens any page, **Then** the browser tab icon is the standard Infrahub icon (added 2026-11-10).

---

### User Story 3 - Set the label and color from the web UI (Priority: P1)

An administrator opens the Global preferences page, enters an instance label, picks a color from a preset list and saves. The new label and color apply to the administrator's own session at once and to other users' sessions without anyone restarting Infrahub or clearing a browser cache. The values survive a restart and an upgrade of Infrahub.

**Why this priority**: The GitHub requester asked to set the label from the settings menu rather than through container variables, so that nobody needs a restart or the permission to restart a container. Deployment defaults set through environment variables were added on 2026-11-10 (User Story 5); a value saved here still overrides them and needs no restart.

**Independent Test**: As an administrator, save a label and a color on the Global preferences page, then open the instance as another user and view the badge and bar; reload the administrator's page and view the saved values in the form.

**Acceptance Scenarios**:

1. **Given** an account that holds the "manage global preferences" permission, **When** it opens the Global preferences page, **Then** the page shows an instance identity section with a label field and a color choice next to the existing date and time settings.
2. **Given** the administrator enters "us-east-1 PROD", picks red and saves, **When** the save completes, **Then** a confirmation is shown, the administrator's own header shows the badge and bar at once, and a reload of the page shows the saved values in the form.
3. **Given** the values were saved, **When** another user focuses an already-open tab of the same instance, **Then** that tab shows the new badge and bar without a manual reload.
4. **Given** the values were saved, **When** Infrahub is restarted or upgraded, **Then** the values are still stored and still shown.
5. **Given** the administrator clears the label and saves, and the deployment sets no default label, **When** the save completes, **Then** the tab title returns to the page title alone and the badge disappears, while the color and the bar are unchanged.
6. **Given** the administrator resets the color and saves, and the deployment sets no default color, **When** the save completes, **Then** the bar disappears and a stored label is shown in the gray badge style.
7. **Given** the administrator changes only the label, **When** the save completes, **Then** the stored color and the date and time settings are unchanged.
8. **Given** the administrator enters a label with leading and trailing spaces, **When** they save, **Then** the stored label has the spaces removed.
9. **Given** the administrator enters only spaces, **When** they save, **Then** the label is reset, as if cleared.
10. **Given** the administrator enters a label longer than 32 characters, **When** they try to save, **Then** the form rejects it with a message that states the limit and nothing is stored.

---

### User Story 4 - Only authorised accounts can change the setting (Priority: P2)

A user who does not hold the "manage global preferences" permission cannot change the instance label or color, from the web UI or through the API, but still views the badge and bar like everyone else.

**Why this priority**: The indicator is a safety signal. If any user could change it, it could not be trusted.

**Independent Test**: As a read-only user, confirm the Global preferences entry is absent from the account menu, the page refuses access, and a direct API write is rejected without changing the stored values.

**Acceptance Scenarios**:

1. **Given** a read-only account, **When** it opens the account menu, **Then** no "Global preferences" entry is shown.
2. **Given** a read-only account, **When** it opens the Global preferences page by URL, **Then** it views an "unauthorized" message and no form.
3. **Given** a read-only account, **When** it sends a write of the instance label through the API, **Then** the write is rejected with the same "not allowed to manage global preferences" error that other global settings use, and the stored values are unchanged.
4. **Given** a super administrator account, **When** it saves the values, **Then** the save succeeds without holding the permission explicitly.
5. **Given** any authenticated account, **When** it tries to store an instance label or color as a personal preference, **Then** the write is rejected: these settings exist only at the instance level.

---

### User Story 5 - Set a default label and color for a deployment (Priority: P2)

Added on 2026-11-10 ([IFC-3588](https://opsmill.atlassian.net/browse/IFC-3588)). An operator deploys each Infrahub instance from its own configuration, such as one Docker Compose file or one set of Helm values per stage. They set `INFRAHUB_INSTANCE_LABEL` and `INFRAHUB_INSTANCE_COLOR` in that configuration, or `label` and `color` in the `[instance]` section of `infrahub.toml`, and the instance shows that label and color from its first start. An administrator can still save a different value on the Global preferences page; the saved value overrides the default until it is reset.

**Why this priority**: Operators who deploy each instance from its own configuration can label it without opening the web UI after each deployment. Without this story, an instance is still labelled from the web UI (User Story 3).

**Independent Test**: Start Infrahub with `INFRAHUB_INSTANCE_LABEL=staging` and `INFRAHUB_INSTANCE_COLOR=AMBER` and nothing saved, open a page and view the badge, the bar and the tab title; save other values on the Global preferences page and view them; reset them and view the defaults again.

**Acceptance Scenarios**:

1. **Given** the deployment sets the default label "staging" and the default color `AMBER`, and nothing is saved, **When** any user opens a page, including the login page, **Then** the badge reads "staging" in the amber style, an amber bar spans the top of the page, the tab title starts with "staging · " and the tab icon is amber.
2. **Given** the same defaults, **When** an administrator saves the label "us-east-1 PROD" and the color red, **Then** every page shows the saved label and color instead of the defaults.
3. **Given** the same defaults, **When** an administrator saves only the label "us-east-1 PROD", **Then** every page shows the saved label in the default amber color: each value is resolved on its own.
4. **Given** saved values that override the defaults, **When** the administrator clears the label, resets the color and saves, **Then** every page shows the default label "staging" and the default color amber again.
5. **Given** the same defaults and nothing saved, **When** an administrator opens the Global preferences page, **Then** the empty label field shows "staging" as its placeholder with the line "Leave empty to use the deployment default: staging.", the color picker reads "Deployment default: Amber", and both fields stay editable.
6. **Given** `INFRAHUB_INSTANCE_LABEL` is longer than 32 characters or contains a control character, **When** Infrahub starts, **Then** it stops and prints a line of the form `<field> | Value error, <message> (value_error)`, where the message starts with "INFRAHUB_INSTANCE_LABEL" and states the rule, for example "Value error, INFRAHUB_INSTANCE_LABEL cannot be longer than 32 characters".
7. **Given** `INFRAHUB_INSTANCE_COLOR` is not one of the preset names in any letter case (for example `PINK`), **When** Infrahub starts, **Then** it stops and prints a line of the same form whose message after "Value error, " is "INFRAHUB_INSTANCE_COLOR must be one of RED, AMBER, GREEN, BLUE, INDIGO, PURPLE, GRAY".
8. **Given** `INFRAHUB_INSTANCE_COLOR` is `red` or ` Red `, **When** Infrahub starts, **Then** the default color is red: the value is trimmed and the letter case is ignored.
9. **Given** `INFRAHUB_INSTANCE_LABEL` or `INFRAHUB_INSTANCE_COLOR` is set to an empty or whitespace-only value, **When** Infrahub starts, **Then** it starts, and that default counts as not set.
10. **Given** the deployment sets defaults, **When** an API client reads the global preferences through GraphQL, **Then** the response contains the saved values only, with `null` for a value that is not saved.

---

### Edge Cases

- The color value is not in the preset list (for example, a hand-written API call sends "pink"): the write is rejected with the GraphQL enum error `Variable '$instance_color' got invalid value 'pink'; Value 'pink' does not exist in 'InstanceColor' enum.`, which does not list the allowed values (the GraphQL schema lists them), and nothing is stored.
- The label contains a line break, another control character (tab, NUL) or a bidirectional text control: the write is rejected.
- The label contains non-ASCII characters (for example "Zürich PROD"): accepted and shown as entered.
- The settings are read before an administrator ever saved anything: the public read returns the deployment defaults, or "no label, no color" when the deployment sets none, without creating a stored record.
- Two administrators save at the same time: the last save wins per field, and no duplicate instance record is created.
- A backup of one instance is restored on another: the label and color stored in the backup are restored too, and an administrator changes them after the restore (product decision, 2026-10-15).
- The browser tab is open while the administrator changes the value: the tab picks the change up the next time it regains focus, not within a guaranteed delay. The 30-second propagation listed in an earlier version of the product card is not a must-have and is not required.
- Dark theme: the badge and bar use the same named color and stay readable in both themes.
- The sidebar is collapsed or the window is narrow: the bar still spans the full width, and the badge keeps a fixed maximum width so the breadcrumb keeps its space.
- The deployment sets a default and an administrator saved a value for the same field: the saved value is shown. A saved label combined with a default color, or the reverse, shows each value from its own source.
- The stored values cannot be read (for example, the database is unavailable): the public read logs the error and serves no label and no color, so the login page still renders without a badge or bar. It does not fall back to the deployment defaults, because a default could name a different stage than the saved value it stands in for. The deployment defaults are still served on their own.
- A deployment default contains surrounding spaces (for example `"  QA  "` or `" GRAY "`): the spaces are removed at startup.
- `INFRAHUB_INSTANCE_COLOR` is written in lowercase or mixed case (`red`, `Red`): accepted as the preset of that name.
- A deployment default is set and an administrator wants no value for that field: not possible from the web UI. An administrator can only replace the default with a saved value, because an empty saved value falls back to the default (the precedence the tech owner chose on 2026-11-10).
- An operator changes `INFRAHUB_INSTANCE_LABEL` or `INFRAHUB_INSTANCE_COLOR`: the change applies after Infrahub restarts. A value an administrator saved in the web UI keeps overriding the new default.
- The label field on the Global preferences page is empty and the deployment sets a default label: the placeholder and the helper line name the default. When the deployment sets no default, the field has no placeholder and no helper line, and the color picker reads "No color".
- The instance color is cleared while a tab is open: the tab icon returns to the standard Infrahub icon at the next configuration fetch.
- Browser support for an SVG tab icon: whether Safari shows the colored icon is not verified.
- An end-to-end test of the deployment defaults does not exist: the end-to-end suite starts one server per session, so a test cannot set a different environment for one test. The defaults are covered by unit and component tests.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The instance settings MUST consist of two independent values: an instance label (free text) and an instance color (one of the presets red, amber, green, blue, indigo, purple, gray). Each MAY be unset.
- **FR-002**: The two values MUST be stored as part of the existing global settings of the instance (the same record that holds the organisation-wide date format and timezone), so that they are kept across restarts and upgrades, are not tied to any branch, and are included in backups and restores.
- **FR-003**: An account MUST be able to change both values only when it holds the "manage global preferences" global permission or is a super administrator. A write by any other account MUST be rejected with the permission error already used for global preferences, and MUST leave the stored values unchanged.
- **FR-004**: The two values MUST be editable on the existing Global preferences page, in a section of their own next to the date and time settings, with the same save and confirmation behaviour as the existing settings.
- **FR-005**: A save MUST allow changing one value without touching the other, and MUST allow resetting each value independently.
- **FR-006**: The label MUST be trimmed of leading and trailing whitespace before validation. An empty or whitespace-only label MUST be treated as a reset. A label longer than 32 characters (counted in code points, as the server counts), or containing a line break, another control character or a bidirectional text control, MUST be rejected with a message that states the rule. Any other character, including non-ASCII, MUST be accepted.
- **FR-007**: A color outside the preset list MUST be rejected with a validation error, and nothing MUST be stored. Through a GraphQL variable the error is the enum coercion error `Variable '$instance_color' got invalid value '<x>'; Value '<x>' does not exist in 'InstanceColor' enum.`, followed by a "Did you mean" hint when the value is close to a member, and it does not list the allowed values, which the GraphQL schema lists.
- **FR-008**: The instance label and color MUST NOT be settable as personal (per-user) preferences and MUST NOT appear in a user's own preferences; a per-user write of either value MUST be rejected.
- **FR-009**: Every visitor, including an anonymous visitor on the login page, MUST be able to read the current label and color, without holding any permission, so that the indicator is shown on every page.
- **FR-010**: A read of the instance settings MUST NOT create a stored record; before the first save, the read returns the deployment defaults (FR-020), or no label and no color when the deployment sets none.
- **FR-011**: When a label is set, the top header of every page inside the application MUST show a badge with the label, styled in the chosen color, or in the neutral gray style when no color is set, and the login page MUST show the same badge near the Infrahub logo on the login card. When no label is set, no badge is rendered. Decision of the tech owner on 2026-11-05: the badge sits on the right of the header, before the task status and repository sync status indicators.
- **FR-012**: When a color is set, every page inside the application and the login page MUST show a thin bar in that color across the full width of the top of the page, above the sidebar and the header. When no color is set, no bar is rendered and no space is reserved.
- **FR-013**: A label that exceeds the badge's maximum width MUST be truncated with an ellipsis, and the full label MUST be available in a tooltip.
- **FR-014**: When a label is set, the browser tab title of every page MUST be "`<label>` · `<page title>`", where the page title is the page's own title or "Infrahub" for pages without one. When no label is set, the tab title MUST be the page title alone, as today.
- **FR-015**: A change saved by an administrator MUST apply to the administrator's own session immediately, and to any other open session the next time it fetches the instance configuration (at least whenever the tab regains focus), without a restart of Infrahub and without clearing a browser cache.
- **FR-016**: The badge and the bar MUST remain readable in the light and dark themes, using the named color consistently in both.
- **FR-017**: The documentation MUST describe the two settings, who can change them, where, the preset list, and MAY suggest a convention (for example red for production) without enforcing it.

Requirements added on 2026-11-10 ([IFC-3588](https://opsmill.atlassian.net/browse/IFC-3588)):

- **FR-018**: The deployment configuration MUST be able to set a default instance label and a default instance color, through the environment variables `INFRAHUB_INSTANCE_LABEL` and `INFRAHUB_INSTANCE_COLOR`, or through `label` and `color` in the `[instance]` section of `infrahub.toml`. A change to a default applies when Infrahub restarts.
- **FR-019**: Infrahub MUST validate both defaults when it loads its configuration at startup. The default label follows the rules of FR-006 (trimmed, at most 32 characters, no control character or bidirectional text control). The default color MUST be one of the names `RED`, `AMBER`, `GREEN`, `BLUE`, `INDIGO`, `PURPLE`, `GRAY`, trimmed and compared without regard to letter case. An invalid value MUST stop Infrahub at startup with an error that names the environment variable and states the rule. An empty or whitespace-only value MUST be treated as not set.
- **FR-020**: The label and the color in effect MUST each be resolved on their own, in this order: the value saved in the global settings, else the deployment default, else no value. FR-011, FR-012 and FR-014 apply to the value in effect. Resetting a saved value (FR-005) MUST make the deployment default apply again.
- **FR-021**: The public instance configuration (FR-009) MUST also include the deployment defaults on their own, so the settings form can name them. The administrator's read of the global settings MUST return the saved values only, so the form can tell a saved value from a default.
- **FR-022**: When the saved values cannot be read, the public instance configuration MUST log the error and serve no label and no color as the values in effect, instead of failing or falling back to the deployment defaults; it MUST still serve the deployment defaults on their own (FR-021).
- **FR-023**: When the deployment sets a default label, the label field on the Global preferences page MUST show it as its placeholder, and, while the field is empty, a helper line "Leave empty to use the deployment default: `<label>`." When the deployment sets a default color, the color picker MUST read "Deployment default: `<Color>`" while no color is selected; otherwise it reads "No color". Both fields MUST stay editable whether or not a default exists.
- **FR-024**: When a color is in effect, the browser tab icon MUST show the Infrahub mark (the outline variant) recolored to that preset. When no color is in effect, the tab icon MUST be the standard Infrahub icon, and removing the color in effect MUST restore it.
- **FR-025**: The documentation MUST describe the two environment variables, the `[instance]` section, the validation at startup, the order in which a value is resolved, the form hints, and the colored tab icon.

### Key Entities *(include if feature involves data)*

- **Global settings record**: the single organisation-wide record that already holds the date format and timezone defaults. It gains two optional values: instance label (text, at most 32 characters after trimming) and instance color (one of seven named presets). It belongs to the instance, not to a branch or a user.
- **Instance configuration served to every visitor**: the public, read-only view of the instance that every client loads before it renders. It gains the label and color in effect and, since 2026-11-10, the deployment defaults on their own.
- **Deployment defaults** (added 2026-11-10): an optional default label and an optional default color read from the deployment configuration when Infrahub starts. They are not stored in the database and do not change the global settings record.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can tell which instance a page belongs to within one second of the page appearing, from the badge and the bar, on 100% of pages including the login page.
- **SC-002**: With several instances open, a user can identify each tab from the tab title alone, without activating the tab.
- **SC-003**: An administrator can set or change the label and color in under one minute from the Global preferences page, with no restart and no help from an operator.
- **SC-004**: After a restart or an upgrade of Infrahub, the label and color are unchanged in 100% of cases.
- **SC-005**: No account without the permission can change the label or color, through the UI or the API, in 100% of attempts.
- **SC-006**: Instances with no label, no color and no deployment default look and behave exactly as before the feature, including the standard tab icon; no existing automated test changes its expectation except where it enumerates the fields of the global settings or the instance configuration. The new form's save button is named "Save instance identity", so tests that locate the "Save" button of the date and time form keep working.

## Assumptions

- The existing "manage global preferences" permission is the right gate; no new permission is created (decision of 2026-11-04).
- The preset list is fixed at red, amber, green, blue, indigo, purple and gray (decision of 2026-11-04). Semantic meanings such as "red means production" are documented suggestions, not enforced.
- The badge sits in the top header (exact position decided in a design jam) and the bar spans the top of the page above the sidebar and the header (decision of 2026-11-04: badge plus thin bar). On the login page the bar spans the top and the badge sits near the logo on the login card.
- Label and color are independent; a color without a label shows the bar only, and a label without a color shows the gray badge only (decision of 2026-11-04).
- The maximum label length is 32 characters, chosen so that a label fits in the header next to the branch selector and leaves room for the page title in a browser tab.
- The separator in the tab title is " · " (space, middle dot, space).
- The anonymous read of the label and color goes through the same public instance configuration that every client already loads before rendering, so the login page shows the indicator and the first tab title already carries the label.
- Propagation to other open sessions relies on the existing refetch when a tab regains focus; no polling interval is added.
- Favicon upload and login page logo upload are out of scope (product decision, 2026-10-15). The colored tab icon of FR-024 is in scope since 2026-11-10: it recolors the Infrahub mark shipped with the frontend and accepts no upload.
- A value saved in the web UI overrides the deployment default; the fields are not locked when a default exists (decision of the tech owner, 2026-11-10).
- Known limitation: While a deployment default is set for a field, the web UI cannot remove that field; it can only replace it with a saved value, because an empty saved value falls back to the default (the precedence the tech owner chose on 2026-11-10).
- The deployment defaults use the same label rules and the same preset list as the saved values, so a value that is valid in one place is valid in the other.
- Changing the label or color does not create an activity log entry; this was an open question on the product card and is not required for 1.13.
