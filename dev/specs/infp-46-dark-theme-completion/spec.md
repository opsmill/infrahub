# Feature Specification: Dark Theme Completion

**Feature Branch**: `dark-theme-completion-infp-46`

**Ticket**: [INFP-46](https://opsmill.atlassian.net/browse/INFP-46)

**Created**: 2026-08-17

**Status**: Draft

**Input**: Follow-up work inherited from the dark-theme series (PRs #10247 → #10284). Seven known
limitations were recorded by the series author; this spec covers all seven.

## Context

A series of eleven merged pull requests tokenized the design system and swept most application
surfaces onto theme-aware CSS custom properties. A twelfth, [#10284](https://github.com/opsmill/infrahub/pull/10284)
("Adapt remaining app to dark theme", 151 files), is open and covers the remaining app surfaces.

The result is a dark palette that exists but that **no user can reach**. Dark mode is activated only
by manually adding a `.dark` class at the top of the cascade, via the development-only
`@custom-variant dark` declaration in the shared theme stylesheet — which carries an explicit
`TODO: DELETE` marker. The series author drove it with a local, uncommitted debug button.

This feature closes that gap and clears the seven limitations the author recorded on handover.

### Relationship to PR #10284

Several items below (notably User Story 5) describe debt that #10284 *introduces* — hastily
dark-themed legacy pages carrying hardcoded variants rather than tokens.

**This work stacks on #10284**: the branch is based on `bab-dark-theme-app` and the pull request
targets it, not `develop`. That makes the debt US5 migrates actually present in the tree, and keeps
this review free of #10284's 151 files. When #10284 merges, this branch re-targets `develop`; if
#10284 is revised, this branch rebases onto it.

Its failing end-to-end checks are explicitly **out of scope** and are not addressed here. ⚠ Stacking
means those failures are inherited and will appear on this pull request too — they are pre-existing,
not caused by this work.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Choose a theme (Priority: P1)

A signed-in user opens their preferences, sees a theme setting alongside the existing date-format and
timezone settings, and picks between light, dark, and matching their operating system. The choice
applies immediately, survives a reload, and follows them to another browser or machine because it is
stored with their account rather than in one browser.

Because the dark palette is known to still contain visual defects, the dark choice is presented as
explicitly pre-release so a user opting in knows what they are accepting.

**Why this priority**: This is the keystone. Every other story either binds a surface to "the
selected theme" or adjusts how that theme looks — none of them are meaningful until a selected theme
exists and is readable by the application.

**Independent Test**: Sign in, change the theme setting, observe the application repaint without a
reload, reload the page and observe the choice persisted, then sign in on a second browser and
observe the same choice.

**Acceptance Scenarios**:

1. **Given** a signed-in user whose theme has never been set, **When** they open their preferences,
   **Then** the theme setting shows the deployment's default as the effective value and indicates
   that it comes from a default rather than from their own choice.
2. **Given** a user viewing the theme setting, **When** they look at the dark option, **Then** it
   carries a visible pre-release marker distinguishing it from the light option.
3. **Given** a user on the light theme, **When** they select dark, **Then** the application switches
   to the dark palette without a page reload.
4. **Given** a user who has selected dark, **When** they reload the page, **Then** the application
   paints in dark from the first frame, with no visible flash of the light theme.
5. **Given** a user who has selected dark in one browser, **When** they sign in from a different
   browser, **Then** the application is dark there too.
6. **Given** a user who has selected "match system", **When** their operating system switches from
   light to dark while the page is open, **Then** the application follows without a reload.
7. **Given** an administrator setting an organisation-wide theme, **When** a user who has made no
   personal choice loads the application, **Then** they see the organisation-wide theme; **and when**
   a user who has made a personal choice loads it, **Then** their personal choice wins.

---

### User Story 2 - Non-production deployments default to dark (Priority: P1)

The team runs non-production builds of Infrahub day to day. Those deployments default to the dark
theme so that the team lives in it continuously and surfaces the remaining visual defects through
ordinary use, without every engineer having to opt in individually. This default ignores the
operating system's appearance deliberately: an engineer on a light system must still see dark, or
they are not dogfooding it.

Production builds default to light. Dark is alpha, so it is reached only by an explicit choice —
never by inference from a user's system setting.

**Why this priority**: This is the stated near-term goal of the whole effort — dogfooding dark for
the coming weeks. It is what converts the setting from a feature into a feedback loop, and it is
cheap once User Story 1 exists.

**Independent Test**: Load a non-production deployment as a user with no theme preference set and
observe dark; load a production build the same way and observe light; in both, set a personal
preference and observe it override the default.

**Acceptance Scenarios**:

1. **Given** a deployment running a non-production build, **When** a user with no theme preference
   loads the application, **Then** it paints in dark **regardless of their system appearance** —
   including for an engineer whose operating system is light.
2. **Given** a deployment running a production build, **When** a user with no theme preference loads
   the application, **Then** it paints in light, **even if their operating system is dark**. Dark is
   alpha and is never reached by inference.
3. **Given** a non-production deployment defaulting to dark, **When** a user explicitly selects
   light, **Then** their choice is honoured and persists.
4. **Given** any deployment, **When** an operator explicitly configures the default theme, **Then**
   that configuration overrides the build-derived default.

---

### User Story 3 - The GraphQL sandbox follows the theme (Priority: P2)

A user working in the GraphQL sandbox on a dark application sees the sandbox in dark too, rather than
a bright panel embedded in a dark page.

**Why this priority**: The sandbox is a full-page surface that is currently pinned to light
regardless of the application theme, making it one of the two most jarring mismatches. It already
ships a dark theme of its own, so the work is binding rather than building.

**Independent Test**: With the application in dark, navigate to the GraphQL sandbox and confirm it
renders dark; switch the theme and confirm the sandbox follows.

**Acceptance Scenarios**:

1. **Given** the application is in dark, **When** the user opens the GraphQL sandbox, **Then** the
   sandbox renders using its dark theme.
2. **Given** the user is in the GraphQL sandbox, **When** they change the application theme, **Then**
   the sandbox switches to match.
3. **Given** the application is in light, **When** the user opens the sandbox, **Then** it renders
   exactly as it does today.

---

### User Story 4 - Mermaid diagrams follow the theme (Priority: P2)

A user reading a document containing a Mermaid diagram on a dark application sees the diagram
rendered for a dark background, with legible text and no bright panel behind it.

**Why this priority**: Same class of mismatch as the sandbox, and diagrams appear inside ordinary
content where a bright block is especially disruptive. Currently only partially dark.

**Independent Test**: With the application in dark, view content containing a Mermaid diagram and
confirm the diagram and its container are dark and legible; switch the theme and confirm the diagram
re-renders to match.

**Acceptance Scenarios**:

1. **Given** the application is in dark, **When** a Mermaid diagram renders, **Then** the diagram
   uses a dark-appropriate palette and its container background matches the surrounding surface.
2. **Given** a rendered Mermaid diagram, **When** the user changes the application theme, **Then**
   the diagram reflects the new theme.
3. **Given** a Mermaid diagram that fails to parse, **When** it renders its error state, **Then**
   that error state is legible in both themes.

---

### User Story 5 - Application surfaces use theme tokens, not hardcoded colors (Priority: P2)

A user moving between pages on a dark application sees one coherent dark theme, rather than pockets
of near-black that were bolted on page by page. Pages carried over from the legacy structure — the
proposed-changes flow, diff and check views, path traversal — look like the rest of the application.

**Why this priority**: This is the largest correctness debt and the most visible source of "almost
dark" defects. Hardcoded per-page variants also mean every future palette change has to be repeated
by hand in each of them, so leaving them in place taxes all later work.

**Independent Test**: With the application in dark, walk the proposed-changes flow, a diff view, the
checks view and path traversal, and confirm each uses the same surfaces, borders and text colors as
the rest of the application. Separately, confirm no application source file specifies theme-specific
colors directly.

**Acceptance Scenarios**:

1. **Given** the application is in dark, **When** the user walks the legacy pages listed above,
   **Then** every surface, border and text color matches the shared palette.
2. **Given** the application source, **When** it is inspected for per-theme color overrides or raw
   color literals in application components, **Then** none remain.
3. **Given** the application is in light, **When** the same pages are compared against their previous
   appearance, **Then** they are visually unchanged.

---

### User Story 6 - The data viewer matches the theme's tone (Priority: P3)

A user viewing file, artifact or object data sees a viewer whose greys belong to the same family as
the rest of the dark theme, rather than a colder panel that reads as a foreign element.

**Why this priority**: A genuine inconsistency, but a tonal one — the viewer is already dark, just
the wrong dark. Lower user impact than surfaces that are still bright.

**Independent Test**: With the application in dark, open the data viewer beside another dark surface
and confirm the greys belong to the same family.

**Acceptance Scenarios**:

1. **Given** the application is in dark, **When** the data viewer renders, **Then** its background,
   border and text colors come from the shared palette.
2. **Given** the data viewer renders any of its content types, **When** each is displayed, **Then**
   none of them shows a fixed light background in dark mode.

---

### User Story 7 - The schema visualizer supports dark (Priority: P3)

A user exploring the schema visualizer on a dark application sees a dark visualizer, consistent with
the application that embeds it.

**Why this priority**: Real, but the longest lead time and the lowest coupling — the visualizer lives
in a separate repository and must be released there before this application can consume it. Deferring
it does not block any other story.

**Independent Test**: With the application in dark, open the schema visualizer and confirm its canvas,
nodes, edges and controls are dark and legible.

**Acceptance Scenarios**:

1. **Given** the application is in dark, **When** the user opens the schema visualizer, **Then** its
   canvas, nodes, edges, labels and controls render in dark and remain legible.
2. **Given** the application is in light, **When** the user opens the visualizer, **Then** it is
   visually unchanged from today.
3. **Given** the visualizer's dark support is released upstream, **When** this application adopts the
   release, **Then** the adoption is a version change here and carries no visualizer styling code in
   this repository.

---

### Edge Cases

The first three are one problem with one answer, so they are grouped rather than listed apart.

- **No account-backed answer yet — before sign-in, on first paint, or when the preference cannot be
  read.** In all three the application must still paint a coherent theme immediately and never land
  half-styled or flash.

  A single mechanism covers all three: a locally cached copy of the last resolved theme, read
  synchronously before the first frame. The account-backed preference reconciles on arrival and
  refreshes the cache. Because the cache holds the *resolved* theme, a returning user — signed in or
  not — paints correctly from the first frame.

  With nothing cached, the fallback is light. On production that is already the deployment default,
  so a first-ever visit is correct. On a non-production deployment it is not: that first visit paints
  light and corrects to dark once the deployment default arrives. Accepted — it is one frame, on the
  team's own builds, on a browser that has never loaded the application before. Removing it would
  mean the server templating the HTML shell, which is disproportionate.

  ⚠ The fallback is light rather than the operating system's appearance. Consulting the system here
  would put a dark-OS user into the alpha palette before any preference has been read — the exact
  inference FR-011 forbids.

- **System appearance changes while the page is open.** A user following their system switches their
  operating system's appearance. The application follows without a reload. Cheap to support —
  the browser exposes this as a subscribable change — so it is in scope rather than deferred.

- **Existing automated tests.** Tests that assert specific colors, or that screenshot the interface,
  are sensitive to the default changing on non-production builds. In scope: the suites must be made
  deterministic rather than left to inherit whatever the build implies.

- **Print and export.** Unchanged; out of scope.

## Requirements *(mandatory)*

### Functional Requirements

**Theme selection and persistence**

- **FR-001**: The system MUST offer a theme preference with three choices: light, dark, and match the
  operating system.
- **FR-002**: The system MUST persist a user's theme choice against their account, so it applies on
  any browser or machine where they sign in.
- **FR-003**: The system MUST support an organisation-wide theme default that applies to users who
  have made no personal choice, and MUST let a personal choice override it. Setting it MUST require
  the same permission as the existing organisation-wide preferences; no new permission is introduced.
- **FR-004**: The system MUST report which layer an effective theme came from — the user's own
  choice, the organisation default, or the built-in default — consistent with how existing
  preferences report their source.
- **FR-005**: Users MUST be able to change the theme and see it applied without reloading the page.
- **FR-006**: The system MUST apply the correct theme on the first painted frame, with no visible
  flash of the other theme.
- **FR-007**: When "match system" is selected, the system MUST follow changes to the operating
  system's appearance while the page is open.
- **FR-008**: The system MUST mark the dark choice as **alpha** in the interface, so users understand
  they are opting into something that may still contain visual defects. The handover named this
  label specifically; "alpha" is the word to render, not a paraphrase of it. Because "match system"
  can resolve to dark, its description MUST make that consequence clear.
- **FR-009**: The system MUST render a coherent theme when no preference can be retrieved, falling
  back to the last locally cached resolution and then to the deployment default. The cache MUST be
  read synchronously before the first frame, and its absence or unavailability MUST NOT prevent the
  application from loading.

**Deployment defaults**

- **FR-010**: Deployments running a non-production build MUST default to dark for users with no
  personal choice.
- **FR-011**: Deployments running a production build MUST default to light. Dark MUST NOT be reached
  without an explicit user choice, because it is alpha.
- **FR-012**: Operators MUST be able to override the build-derived default with explicit
  configuration.
- **FR-013**: A deployment default MUST NOT overwrite or reset any user's stored personal choice.

**Embedded and third-party surfaces**

- **FR-014**: The GraphQL sandbox MUST render in the application's active theme, and MUST follow
  changes to it. It MUST NOT be pinned to a fixed theme.
- **FR-015**: Mermaid diagrams MUST render using a palette appropriate to the active theme, including
  their container background and their parse-error state, and MUST reflect a theme change.
- **FR-016**: The schema visualizer MUST support both themes and follow the embedding application's
  active theme. Its styling MUST be implemented in its own repository and consumed here as a released
  version.

**Token discipline**

- **FR-017**: Application components MUST express color through shared theme tokens. Per-theme
  overrides and raw color literals MUST NOT remain in application components.
- **FR-018**: The data viewer MUST draw its surfaces, borders and text from the shared palette, and
  MUST NOT present a fixed light background in any of its content types.
- **FR-019**: The development-only mechanism that currently makes the dark palette reachable MUST be
  removed once the theme preference supersedes it.

**Preservation**

- **FR-020**: The light theme MUST remain visually unchanged by this feature.
- **FR-021**: Text and essential interface elements MUST remain legible against their background in
  both themes, meeting the contrast level the light theme already achieves.

  This is about text against a surface, not about telling semantic colors apart from each other.
  Content that carries its own colors — diagrams, syntax highlighting, status and severity palettes,
  user-supplied content — is **out of scope** and tracked separately; a migration here must not make
  those worse, but redesigning them is not this feature's job.

### Key Entities

- **Theme preference**: A user's chosen appearance. One of light, dark, or match-system. Stored per
  account and, separately, once for the organisation. Absent by default; absence means "fall back".
- **Effective theme**: The appearance actually applied for a given user at a given moment. Resolved
  from the user's choice, then the organisation default, then the deployment default; and if the
  resolved choice is match-system, further resolved against the operating system's current
  appearance.
- **Deployment default theme**: The appearance applied to users who have expressed no choice.
  Derived from whether the running build is a production release, and overridable by operator
  configuration.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can change the theme and see the whole application — including the GraphQL
  sandbox, Mermaid diagrams and the schema visualizer — reflect the change, without reloading.
- **SC-002**: On reload, the correct theme is present in the first painted frame; no flash of the
  opposite theme is observable. This is verified by an automated end-to-end check, not by manual
  observation alone — it is the requirement most likely to regress silently, and the mechanism that
  delivers it runs outside the unit-test harness.
- **SC-003**: A theme chosen on one machine is in effect when the same user signs in on another.
- **SC-004**: Zero application components specify per-theme color overrides or raw color literals;
  this is verifiable by inspection of the source and holds as a standing property, not a one-time
  cleanup.
- **SC-005**: The light theme is unchanged: a comparison of light-theme rendering before and after
  this feature shows no visual differences.
- **SC-006**: Every page reachable from the main navigation renders with no bright-on-dark surface
  when dark is active.
- **SC-007**: Non-production deployments present dark to a user with no stored preference, and
  production deployments present light, without either altering stored preferences and without
  either consulting the operating system.
- **SC-008**: The team can run a non-production deployment in dark continuously for the dogfooding
  period without needing per-engineer setup.
- **SC-009**: Text and essential interface elements meet the same contrast level in dark as the light
  theme already achieves, verified across the pages walked for SC-006 rather than on a sample.

## Assumptions

These were decided during specification rather than left open. Each is a judgement call that a
reviewer may overturn.

- **Dark is never reached by inference.** Because it is alpha, a user arrives at it only by choosing
  it — either by selecting dark, or by selecting match-system on a dark operating system. Production
  therefore defaults to light rather than to the system appearance, and the alpha tag always labels
  something the user actually chose.

  An intermediate revision of this spec defaulted production to the system appearance. That was
  withdrawn once the consequence was made explicit: it would have put dark-OS production users into
  the alpha palette without any choice on their part, which is precisely what the alpha label exists
  to prevent.
- **The non-production default ignores the operating system deliberately.** Following the system on
  non-production builds would leave every engineer on a light system out of the dogfooding, which is
  the entire purpose of that default.
- **Three choices, not two.** Match-system is included rather than deferred: it is the conventional
  expectation for a theme setting, and adding it later would change the meaning of an already-stored
  value. It is available on every deployment, but only ever as an explicit choice — never a default.
- **The existing preference machinery is extended, not replaced.** Theme joins date-format and
  timezone in the established two-layer user/organisation preference model, and inherits its
  resolution and source-reporting semantics.
- **"Non-production build" is derived from the running version**, not from a separate deployment
  flag, so that no additional configuration is required for the common case. Explicit configuration
  remains available as an override. The precise derivation is a design decision for the plan.
- **This work stacks on PR #10284.** The branch is based on `bab-dark-theme-app` and the pull request
  targets it, rather than `develop`. #10284's surfaces are the input to User Story 5, and its failing
  end-to-end checks are out of scope. When #10284 merges, this branch re-targets `develop`.
- **The schema visualizer is a separate deliverable.** Upstream release precedes adoption here; the
  adoption in this repository is a dependency version change with no styling code.
- **Print, export and screenshot output are unchanged.**

## Dependencies

- PR [#10284](https://github.com/opsmill/infrahub/pull/10284) merged.
- The existing account-backed preference system (user and organisation layers, effective resolution,
  source reporting).
- The existing build-version information already exposed by the backend.
- The `opsmill/infrahub-schema-visualizer` repository, for User Story 7 only. That story completes on
  the upstream repository's timeline, not this one, so it is tracked as its own deliverable and does
  not gate the other six. It remains in scope — the seven-item scope was proposed narrower, queried,
  and confirmed at all seven by the requester.

## Out of Scope

- The failing end-to-end checks on PR #10284.
- Any change to the light theme's appearance.
- **Content that carries its own colors** — diagrams, syntax highlighting, status and severity
  palettes, user-supplied content. Making these meaningful in both themes is a separate piece of
  work. This feature must not degrade them, but does not redesign them.
- **Cross-tab synchronisation.** A second open tab is not required to react to a theme change made in
  the first; it picks the change up on its next load.
- Additional themes beyond light and dark (high contrast, custom palettes, per-branch theming).
- Theming of printed or exported output.
- Restyling third-party surfaces beyond binding them to the active theme.
