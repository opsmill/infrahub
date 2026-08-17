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

Because the dark palette is known to still contain visual defects, the dark choice is tagged **alpha**
so a user opting in knows what they are accepting.

**Why this priority**: This is the keystone. Every other story either binds a surface to "the
selected theme" or adjusts how that theme looks — none of them are meaningful until a selected theme
exists and is readable by the application.

**Independent Test**: Sign in, change the theme setting, observe the application repaint without a
reload, reload the page and observe the choice persisted, then sign in on a second browser and
observe the same choice.

**Acceptance Scenarios**:

1. **Given** a signed-in user whose theme has never been set, **When** they open their preferences,
   **Then** the theme setting shows the effective value and indicates that it comes from a default
   rather than from their own choice.
2. **Given** a user viewing the theme setting, **When** they look at the dark option, **Then** it
   carries a visible **alpha** marker distinguishing it from the light option.
3. **Given** a user on the light theme, **When** they select dark, **Then** the application switches
   to the dark palette without a page reload.
4. **Given** a user who has selected dark, **When** they reload the page, **Then** the application
   paints in dark from the first frame, with no visible flash of the light theme.
5. **Given** a user who has selected dark in one browser, **When** they sign in from a different
   browser, **Then** the application is dark there too.
6. **Given** a user who has selected "match system", **When** their operating system switches from
   light to dark while the page is open, **Then** the application follows without a reload.
7. **Given** a user who has selected a theme, **When** they clear it back to the inherited default,
   **Then** the setting reports the value as coming from a default again rather than from their own
   choice.

---

### User Story 2 - The whole feature sits behind a flag, on for the dev stack (Priority: P1)

The theme feature is gated by an experimental flag. It is off by default everywhere, and turned on in
the development stack so the team lives in dark continuously and surfaces its remaining visual
defects through ordinary use, without any engineer configuring anything themselves.

The flag does two jobs while dark is alpha: it decides whether the feature exists at all, and — where
it exists — it makes dark the default for anyone who has not chosen. With the flag off there is no
theme setting and the application is light. Both are deliberate: an engineer on a light system must
still see dark or they are not dogfooding it, and a user on a deployment where the flag is off must
have no route into the alpha palette at all.

**Why this priority**: This is the stated near-term goal — dogfooding dark for the coming weeks — and
it is what keeps an unfinished theme away from anyone who has not opted into running it.

Defects found this way are reported over Slack. Naming the destination is what makes "no new defects
were found" a claim someone can check rather than an absence of evidence.

**Independent Test**: Start the dev stack with no per-engineer setup and observe dark; start with the
flag off and observe light with no theme setting present; in both, confirm a stored preference is
never destroyed.

**Acceptance Scenarios**:

1. **Given** a deployment with the flag on and a user with no theme preference, **When** they load the
   application, **Then** it paints dark **regardless of their system appearance** — including for an
   engineer whose operating system is light.
2. **Given** a deployment with the flag off, **When** any user loads the application, **Then** it
   paints light and **no theme setting is offered**. In particular "match system" is absent, so a
   user on a dark operating system has no route to the alpha palette.
3. **Given** the flag is on and a user has selected dark, **When** an operator turns the flag off,
   **Then** the application renders light **and the stored preference is retained, not deleted** —
   turning the flag back on restores their choice.
4. **Given** a deployment with the flag on defaulting to dark, **When** a user explicitly selects
   light, **Then** their choice is honoured and persists.
5. **Given** an engineer starting the development stack, **When** they do nothing else, **Then** the
   application is dark — no per-engineer configuration step exists.

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

  With nothing cached, the fallback is light. With the flag off that is already the answer, so the
  first-ever visit is correct. With the flag on it is not: that first visit paints light and corrects
  to dark once the flag's value arrives. Accepted — it is one frame, on a flag-enabled deployment, on
  a browser that has never loaded the application before. Removing it would mean the server
  templating the HTML shell, which is disproportionate.

  ⚠ The fallback is light rather than the operating system's appearance. Consulting the system here
  would put a dark-OS user into the alpha palette before either the preference or the flag has been
  read — exactly what FR-011 exists to prevent.

- **The flag is turned off while a user has dark stored.** The application renders light; the stored
  preference is retained untouched and honoured again if the flag returns. A config change must
  never destroy user data.

- **System appearance changes while the page is open.** A user who chose match-system switches their
  operating system's appearance. The application follows without a reload. Cheap to support — the
  browser exposes this as a subscribable change — so it is in scope rather than deferred.

- **Existing automated tests.** Tests that assert specific colors, or that screenshot the interface,
  are sensitive to the flag's value. In scope: the suites must pin the theme explicitly rather than
  inherit whatever the deployment implies.

- **Print and export.** Unchanged; out of scope.

## Requirements *(mandatory)*

### Functional Requirements

**Theme selection and persistence**

- **FR-001**: The system MUST offer a theme preference with three choices: light, dark, and match the
  operating system.
- **FR-002**: The system MUST persist a user's theme choice against their account, so it applies on
  any browser or machine where they sign in.
- **FR-003**: The theme preference MUST be user-scoped only. No organisation-wide theme default is
  offered in this version — while the feature is flag-gated to the development stack there is no
  administrator setting a house theme for anyone. This is deferred to the moment the flag is removed,
  when a real user for it exists.
- **FR-004**: The system MUST report which layer an effective theme came from — the user's own
  choice or the built-in default — consistent with how existing preferences report their source. No
  new permission is introduced.
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
  back to the last locally cached resolution and then to light. The cache MUST be read synchronously
  before the first frame, and its absence or unavailability MUST NOT prevent the application from
  loading.

**Feature flag**

- **FR-010**: The theme feature MUST be gated by an experimental flag, following the convention the
  existing experimental settings already use: off by default, enabled per deployment through
  configuration. The development stack MUST enable it, so an engineer gets dark by starting the
  stack and performing no other step.
- **FR-011**: With the flag off, the system MUST render light and MUST NOT offer a theme setting at
  all. Offering only "light" and "match system" is not sufficient: a user on a dark operating system
  would reach the alpha palette through match-system, defeating the flag.
- **FR-012**: With the flag on, the system MUST default to dark for users with no personal choice,
  **regardless of their operating system's appearance**. Following the system here would leave every
  engineer on a light machine out of the dogfooding, which is the flag's whole purpose.
- **FR-013**: Changing the flag MUST NOT overwrite, reset or delete any user's stored preference. A
  stored choice that the flag makes unreachable MUST be ignored while the flag is off and honoured
  again when it returns.

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
  account only. Absent by default; absence means "fall back".
- **Effective theme**: The appearance actually applied for a given user at a given moment. Resolved
  from the user's choice, then the flag's default; and if the resolved choice is match-system,
  further resolved against the operating system's current appearance.
- **Theme feature flag**: A per-deployment switch, off by default and enabled by configuration. While
  dark is alpha it decides both whether the feature exists and, where it does, that dark is the
  default for users who have not chosen. It is never stored against a user and never modifies what
  is stored against one.

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
- **SC-007**: With the flag on, a user with no stored preference sees dark whatever their operating
  system says; with the flag off, every user sees light and no theme setting exists. Neither state
  alters a stored preference, and neither consults the operating system.
- **SC-008**: An engineer gets dark by starting the development stack and taking **zero** further
  configuration steps. Counted literally: the number of actions between "stack is up" and "interface
  is dark" is nought.
- **SC-009**: Text and essential interface elements meet the same contrast level in dark as the light
  theme already achieves, verified across the pages walked for SC-006 rather than on a sample.

## Assumptions

These were decided during specification rather than left open. Each is a judgement call that a
reviewer may overturn.

- **Dark is never reached by inference.** Because it is alpha, a user arrives at it only by choosing
  it — either by selecting dark, or by selecting match-system on a dark operating system. Where the
  flag is off there is no route in at all; where it is on, the deployment has opted in on the user's
  behalf. The alpha tag therefore always labels something someone actually chose.

  An intermediate revision defaulted production to the system appearance. It was withdrawn once the
  consequence was explicit: it would have put dark-OS users into the alpha palette with no choice on
  their part, which is precisely what the alpha label exists to prevent.
- **The flag's default ignores the operating system deliberately.** Following the system would leave
  every engineer on a light machine out of the dogfooding, which is the flag's entire purpose.
- **Three choices, not two.** Match-system is included rather than deferred: it is the conventional
  expectation for a theme setting, and adding it later would change the meaning of an already-stored
  value. It is offered only where the flag is on, and only ever as an explicit choice — never a
  default.
- **The existing preference machinery is extended, not replaced.** Theme joins date-format and
  timezone in the established preference model and inherits its resolution and source-reporting
  semantics — but is exposed at the user scope only.
- **The flag follows the existing experimental-settings convention** rather than deriving from the
  running version. The two experimental settings already in the codebase default to `false` and are
  enabled per deployment through configuration; this one does the same, and the development stack
  enables it.

  An earlier revision derived the default from the version's pre-release status. It was withdrawn
  because "pre-release" catches any beta or release candidate — including one a customer runs in
  their own environment — which is broader than "the deployments we run". Following the existing
  convention targets exactly the intended deployments, matches how the codebase already works, and
  removes a subsystem. The accepted trade: deployments not started from this repository's
  configuration files are not covered and stay light unless configured.
- **The flag has no removal date, knowingly.** It is recorded as open-ended rather than tied to a
  release, because the release cycle for the version this would land in is not yet known. ⚠ The same
  settings class already contains a dead experimental flag carrying a deprecation notice, so
  flag-rot here is a realised failure mode rather than a hypothetical one.
- **This work stacks on PR #10284.** The branch is based on `bab-dark-theme-app` and the pull request
  targets it, rather than `develop`. #10284's surfaces are the input to User Story 5, and its failing
  end-to-end checks are out of scope. When #10284 merges, this branch re-targets `develop`.
- **The schema visualizer is a separate deliverable.** Upstream release precedes adoption here; the
  adoption in this repository is a dependency version change with no styling code.
- **Print, export and screenshot output are unchanged.**

## Dependencies

- PR [#10284](https://github.com/opsmill/infrahub/pull/10284) — stacked on, not waited for.
- The existing account-backed preference system (effective resolution, source reporting), used at the
  user scope only.
- The existing experimental-settings mechanism, already surfaced to the frontend before sign-in.
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
- **An organisation-wide theme default.** While the feature is flag-gated there is no administrator
  setting a house theme for anyone. Deferred to the moment the flag is removed, when a real user for
  it exists. The backend gains it for free either way — the preference mutation's scope argument is
  shared — so this defers only the interface for it.
- **A removal date for the flag**, recorded as knowingly open-ended rather than left unstated.
- Additional themes beyond light and dark (high contrast, custom palettes, per-branch theming).
- Theming of printed or exported output.
- Restyling third-party surfaces beyond binding them to the active theme.
