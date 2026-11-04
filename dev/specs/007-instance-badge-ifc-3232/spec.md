# Feature Specification: Instance label and color as global settings

**Feature Branch**: `ple-instance-badge-ifc-3232` (spec directory `007-instance-badge-ifc-3232`)

**Created**: 2026-11-04

**Status**: Draft

**Input**: User description: "Instance label and color as new global settings (IFC-3232, product card INFP-538). An administrator with the manage_global_preferences permission sets an instance label (free text, max 32 chars, trimmed, empty = reset) and an instance color (preset: red, amber, green, blue, indigo, purple, gray) on the Global preferences page; both are stored with the global settings and take effect without a restart. Every visitor, including on the login page, views a badge with the label in the header and a thin full-width colored bar at the top of the page, and the browser tab title becomes `<label> · <page title>`. Fields are independent. Reset restores "Infrahub" and no badge or bar. Out of scope: favicon and login logo upload."

**Sources**: [IFC-3232](https://opsmill.atlassian.net/browse/IFC-3232) (mirrored from [opsmill/infrahub#10690](https://github.com/opsmill/infrahub/issues/10690)), product card [INFP-538](https://opsmill.atlassian.net/browse/INFP-538), decisions taken with the tech owner on 2026-11-04.

## Problem

Teams run several Infrahub instances: one per stage (development, QA, production) or one per region. Their users open several of them in one browser, and every tab reads "Infrahub" with the same look. Nothing in the web UI says which instance a tab shows, so users check the URL before every change, and a change meant for QA can land in production. Three customers asked for a way to tell instances apart, in particular during a schema upgrade and when they move from one instance to another.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tell instances apart on every page (Priority: P1)

A user who works in several Infrahub instances opens one of them. On every page, including the login page, they view a badge with the instance label in the top header and a thin colored bar across the top of the page. The color is the one the administrator chose for this instance, so a user who has learned "red is production" knows at a glance where they are before they change data.

**Why this priority**: This is the customer need itself. Without the indicator on the page, the setting has no value.

**Independent Test**: With a label and a color stored for the instance, open any page as any user (administrator, read-only user, anonymous visitor on the login page) and view the badge text and the bar color. Reload the page and view the same.

**Acceptance Scenarios**:

1. **Given** the instance label is "us-east-1 PROD" and the color is red, **When** a read-only user opens the branches page, **Then** the top header shows a badge reading "us-east-1 PROD" in the red style and a thin red bar spans the full width at the top of the page.
2. **Given** the same settings, **When** an anonymous visitor opens the login page, **Then** the login page shows the thin red bar at the top and the badge with the label.
3. **Given** the same settings, **When** the user reloads the page or navigates to another page, **Then** the badge and the bar are still shown.
4. **Given** no label and no color are stored, **When** any user opens any page, **Then** no badge and no bar are rendered, and the layout is identical to today.
5. **Given** a color is stored but no label, **When** a user opens a page, **Then** only the bar is shown, in that color.
6. **Given** a label is stored but no color, **When** a user opens a page, **Then** only the badge is shown, in the neutral gray style, and no bar.
7. **Given** a label longer than the badge can display at the header width, **When** a user hovers the badge, **Then** the badge shows the label truncated with an ellipsis and a tooltip shows the full label.

---

### User Story 2 - Tell browser tabs apart (Priority: P1)

A user has tabs of several instances open. Each tab title starts with the label of its instance, followed by the page title, so the tabs can be told apart in the tab bar and in the browser history.

**Why this priority**: The tab title is the only indicator visible when the page itself is not in front of the user, and the GitHub request and the product card both list it as a must-have.

**Independent Test**: With a label stored, open a page and read the document title; clear the label and read it again.

**Acceptance Scenarios**:

1. **Given** the label is "QA", **When** a user opens the schema page, **Then** the tab title is "QA · Schema".
2. **Given** the label is "QA", **When** a user opens a page that has no page title of its own, **Then** the tab title is "QA · Infrahub".
3. **Given** no label is stored, **When** a user opens the schema page, **Then** the tab title is "Schema", exactly as today.
4. **Given** the label is "QA" and the user navigates from the schema page to a page without its own title, **Then** the tab title changes from "QA · Schema" to "QA · Infrahub", never to a title without the label.

---

### User Story 3 - Set the label and color from the web UI (Priority: P1)

An administrator opens the Global preferences page, enters an instance label, picks a color from a preset list and saves. The new label and color apply to the administrator's own session at once and to other users' sessions without anyone restarting Infrahub or clearing a browser cache. The values survive a restart and an upgrade of Infrahub.

**Why this priority**: The GitHub requester asked to set the label from the settings menu rather than through container variables, so that nobody needs a restart or the permission to restart a container.

**Independent Test**: As an administrator, save a label and a color on the Global preferences page, then open the instance as another user and view the badge and bar; reload the administrator's page and view the saved values in the form.

**Acceptance Scenarios**:

1. **Given** an account that holds the "manage global preferences" permission, **When** it opens the Global preferences page, **Then** the page shows an instance identity section with a label field and a color choice next to the existing date and time settings.
2. **Given** the administrator enters "us-east-1 PROD", picks red and saves, **When** the save completes, **Then** a confirmation is shown, the administrator's own header shows the badge and bar at once, and a reload of the page shows the saved values in the form.
3. **Given** the values were saved, **When** another user focuses an already-open tab of the same instance, **Then** that tab shows the new badge and bar without a manual reload.
4. **Given** the values were saved, **When** Infrahub is restarted or upgraded, **Then** the values are still stored and still shown.
5. **Given** the administrator clears the label and saves, **When** the save completes, **Then** the tab title returns to the page title alone and the badge disappears, while the color and the bar are unchanged.
6. **Given** the administrator resets the color and saves, **When** the save completes, **Then** the bar disappears and a stored label is shown in the gray badge style.
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

### Edge Cases

- The color value is not in the preset list (for example, a hand-written API call sends "pink"): the write is rejected with a validation error naming the allowed values, and nothing is stored.
- The label contains a line break: the write is rejected.
- The label contains non-ASCII characters (for example "Zürich PROD"): accepted and shown as entered.
- The settings are read before an administrator ever saved anything: the read returns "no label, no color" without creating a stored record.
- Two administrators save at the same time: the last save wins per field, and no duplicate instance record is created.
- A backup of one instance is restored on another: the label and color stored in the backup are restored too, and an administrator changes them after the restore (product decision, 2026-10-15).
- The browser tab is open while the administrator changes the value: the tab picks the change up the next time it regains focus, not within a guaranteed delay. The 30-second propagation listed in an earlier version of the product card is not a must-have and is not required.
- Dark theme: the badge and bar use the same named color and stay readable in both themes.
- The sidebar is collapsed or the window is narrow: the bar still spans the full width, and the badge keeps a fixed maximum width so the breadcrumb keeps its space.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The instance settings MUST consist of two independent values: an instance label (free text) and an instance color (one of the presets red, amber, green, blue, indigo, purple, gray). Each MAY be unset.
- **FR-002**: The two values MUST be stored as part of the existing global settings of the instance (the same record that holds the organisation-wide date format and timezone), so that they are kept across restarts and upgrades, are not tied to any branch, and are included in backups and restores.
- **FR-003**: An account MUST be able to change both values only when it holds the "manage global preferences" global permission or is a super administrator. A write by any other account MUST be rejected with the permission error already used for global preferences, and MUST leave the stored values unchanged.
- **FR-004**: The two values MUST be editable on the existing Global preferences page, in a section of their own next to the date and time settings, with the same save and confirmation behaviour as the existing settings.
- **FR-005**: A save MUST allow changing one value without touching the other, and MUST allow resetting each value independently.
- **FR-006**: The label MUST be trimmed of leading and trailing whitespace before validation. An empty or whitespace-only label MUST be treated as a reset. A label longer than 32 characters or containing a line break MUST be rejected with a message that states the rule. Any other character, including non-ASCII, MUST be accepted.
- **FR-007**: A color outside the preset list MUST be rejected with a validation error that lists the allowed values.
- **FR-008**: The instance label and color MUST NOT be settable as personal (per-user) preferences and MUST NOT appear in a user's own preferences; a per-user write of either value MUST be rejected.
- **FR-009**: Every visitor, including an anonymous visitor on the login page, MUST be able to read the current label and color, without holding any permission, so that the indicator is shown on every page.
- **FR-010**: A read of the instance settings MUST NOT create a stored record; before the first save, the read returns no label and no color.
- **FR-011**: When a label is set, the top header of every page inside the application and the login page MUST show a badge with the label, styled in the chosen color, or in the neutral gray style when no color is set. When no label is set, no badge is rendered.
- **FR-012**: When a color is set, every page inside the application and the login page MUST show a thin bar in that color across the full width of the top of the page, above the sidebar and the header. When no color is set, no bar is rendered and no space is reserved.
- **FR-013**: A label that exceeds the badge's maximum width MUST be truncated with an ellipsis, and the full label MUST be available in a tooltip.
- **FR-014**: When a label is set, the browser tab title of every page MUST be "`<label>` · `<page title>`", where the page title is the page's own title or "Infrahub" for pages without one. When no label is set, the tab title MUST be the page title alone, as today.
- **FR-015**: A change saved by an administrator MUST apply to the administrator's own session immediately, and to any other open session the next time it fetches the instance configuration (at least whenever the tab regains focus), without a restart of Infrahub and without clearing a browser cache.
- **FR-016**: The badge and the bar MUST remain readable in the light and dark themes, using the named color consistently in both.
- **FR-017**: The documentation MUST describe the two settings, who can change them, where, the preset list, and MAY suggest a convention (for example red for production) without enforcing it.

### Key Entities *(include if feature involves data)*

- **Global settings record**: the single organisation-wide record that already holds the date format and timezone defaults. It gains two optional values: instance label (text, at most 32 characters after trimming) and instance color (one of seven named presets). It belongs to the instance, not to a branch or a user.
- **Instance configuration served to every visitor**: the public, read-only view of the instance that every client loads before it renders. It gains the current label and color.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can tell which instance a page belongs to within one second of the page appearing, from the badge and the bar, on 100% of pages including the login page.
- **SC-002**: With several instances open, a user can identify each tab from the tab title alone, without activating the tab.
- **SC-003**: An administrator can set or change the label and color in under one minute from the Global preferences page, with no restart and no help from an operator.
- **SC-004**: After a restart or an upgrade of Infrahub, the label and color are unchanged in 100% of cases.
- **SC-005**: No account without the permission can change the label or color, through the UI or the API, in 100% of attempts.
- **SC-006**: Instances with no label and no color look and behave exactly as before the feature; no existing automated test changes its expectation except where it enumerates the fields of the global settings or the instance configuration.

## Assumptions

- The existing "manage global preferences" permission is the right gate; no new permission is created (decision of 2026-11-04).
- The preset list is fixed at red, amber, green, blue, indigo, purple and gray (decision of 2026-11-04). Semantic meanings such as "red means production" are documented suggestions, not enforced.
- The badge sits in the top header and the bar spans the top of the page above the sidebar and the header (decision of 2026-11-04: badge plus thin bar).
- Label and color are independent; a color without a label shows the bar only, and a label without a color shows the gray badge only (decision of 2026-11-04).
- The maximum label length is 32 characters, chosen so that a label fits in the header next to the branch selector and leaves room for the page title in a browser tab.
- The separator in the tab title is " · " (space, middle dot, space).
- The anonymous read of the label and color goes through the same public instance configuration that every client already loads before rendering, so the login page shows the indicator and the first tab title already carries the label.
- Propagation to other open sessions relies on the existing refetch when a tab regains focus; no polling interval is added.
- Favicon upload and login page logo upload are out of scope (product decision, 2026-10-15).
- Changing the label or color does not create an activity log entry; this was an open question on the product card and is not required for 1.13.
