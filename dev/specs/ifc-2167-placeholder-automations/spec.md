# Feature Specification: Record template fingerprints in the database instead of placeholder automations

**Feature Branch**: `claude/friendly-goodall-b7a3eu`

**Created**: 2026-11-19

**Status**: Draft

**Input**: Jira epic [IFC-2167](https://opsmill.atlassian.net/browse/IFC-2167) "Refactor placeholder automations", which implements the discovery idea [INFP-441](https://opsmill.atlassian.net/browse/INFP-441). The epic has no description of its own. INFP-441 states: "Currently have high number of Prefect automations serving only as placeholders to track when to trigger recalculation of display labels and HFIDs. [...] With multiple nodes and branch replicas, easy to end up with hundreds of automations. Goal is to store these as StandardNode objects in database instead." Related tech-debt cards: [INBOX-6](https://opsmill.atlassian.net/browse/INBOX-6), [INBOX-68](https://opsmill.atlassian.net/browse/INBOX-68).

## Background

When a schema defines a display label template, a human-friendly ID (HFID), or a Jinja2 computed attribute, Infrahub has to recompute the stored value of every node of that kind whenever the template is added or changed. To detect that change, Infrahub creates one automation in the task manager per kind (and per computed attribute) on the default branch, and one more on each branch whose schema differs from the default branch. These automations never run: their event filter matches a field name that no node has. They exist only so that their description can hold a fingerprint of the template. For display labels and HFIDs, on each schema update, Infrahub compares the fingerprint in the schema with the fingerprint in the automation and, when they differ, recomputes every node of the kind. For Jinja2 computed attributes, the recompute is decided from the schema and the elements that the schema update changed; the fingerprint is used only to skip a branch whose template matches the default branch, and the gathered trigger definitions provide that value as well.

Sources for the current behavior:

- Display labels and HFIDs: `dev/knowledge/backend/display-labels-and-hfid.md` (section "Async Backfill After Schema Changes").
- Jinja2 computed attributes: `dev/knowledge/backend/computed-attributes.md` (the paragraph on self-targeting triggers).
- One automation per diverging branch: `dev/knowledge/backend/events.md` (section "Branch scoping of automations").

According to INFP-441, one customer reached 11,000 automations and parts of the system stopped working during the 1.5 upgrade, and the task manager UI lists only the first 200 automations in alphabetical order, which hides the automations an operator needs when troubleshooting.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Keep the task manager free of automations that never run (Priority: P1)

An operator runs Infrahub with many node kinds that define display labels, HFIDs or Jinja2 computed attributes, and with many branches whose schema differs from the default branch. The operator opens the automations list in the task manager to troubleshoot a Generator, a webhook or a computed attribute that did not run. Today, most of the list consists of automations that never run, and the list stops at 200 entries. After the change, the list contains only automations that react to events, so the operator finds the automation they are looking for.

**Why this priority**: This is the problem stated in INFP-441: the automation count grows with the number of kinds multiplied by the number of diverging branches, and it already broke an upgrade for one customer.

**Independent Test**: On an instance with a schema that defines display labels, HFIDs and Jinja2 computed attributes on several kinds, and with two branches that each carry a schema change, count the automations in the task manager. No automation exists whose only role is to hold a template fingerprint, and the number of automations does not change when a new kind is loaded whose display label template reads only attributes of its own node.

**Acceptance Scenarios**:

1. **Given** a schema with display label templates on 50 kinds, **When** the schema is loaded, **Then** the task manager holds no automation per kind for display label change detection.
2. **Given** a schema with HFIDs on 50 kinds and Jinja2 computed attributes that read only attributes of their own node, **When** the schema is loaded, **Then** the task manager holds no automation per kind or per computed attribute for change detection.
3. **Given** the default branch and three branches whose schema differs from the default branch, **When** each branch's schema is loaded, **Then** the number of automations in the task manager does not grow with the number of kinds that define a display label, an HFID or a Jinja2 computed attribute that reads only its own node.
4. **Given** a display label template that reads an attribute of a peer (for example a device label that reads the name of its role), **When** the schema is loaded, **Then** the automation that recomputes the label when that peer attribute changes still exists, because that automation runs.

---

### User Story 2 - Stored values are recomputed exactly when a template changes (Priority: P1)

A schema designer changes the display label template of a kind, adds an HFID to a kind, or changes the template of a Jinja2 computed attribute. As today, Infrahub recomputes the stored value of every node of that kind on the branch where the schema changed, and does not recompute kinds whose templates did not change.

**Why this priority**: Removing the placeholder automations must not change when the values that users view in the UI, in GraphQL results and in artifacts are recomputed. A missed recompute leaves stale labels; an extra recompute loads the task workers.

**Independent Test**: Load a schema, then load a second version that changes only the display label template of one kind. Check that the nodes of that kind show the new label, and that no recompute was submitted for any other kind or for HFIDs or computed attributes.

**Acceptance Scenarios**:

1. **Given** a kind with a display label template on the default branch, **When** a schema update changes that template, **Then** every node of the kind on the default branch has its stored display label recomputed with the new template.
2. **Given** a kind without an HFID, **When** a schema update adds an HFID to the kind, **Then** every node of the kind has its stored HFID computed.
3. **Given** a Jinja2 computed attribute that reads only attributes of its own node, **When** a schema update changes its template, **Then** every node of the kind has the attribute recomputed. As today, this recompute is decided from the elements that the schema update changed, not from a recorded fingerprint.
4. **Given** a schema update that changes no template, **When** Infrahub processes the update, **Then** no display label, HFID or Jinja2 computed attribute recompute is submitted.
5. **Given** a branch whose schema differs from the default branch but whose template for a kind is identical to the default branch template, **When** the branch schema is loaded, **Then** no recompute is submitted for that kind on that branch, as today.
6. **Given** a branch whose template for a kind differs from the default branch template, **When** the branch schema is loaded, **Then** every node of that kind on that branch is recomputed, and the nodes on the default branch are not.
7. **Given** a schema update that changes the display label template of one kind and the HFID of another, **When** Infrahub processes the update, **Then** exactly one recompute is submitted for each of the two changes.

---

### User Story 3 - Upgrade an existing instance without a full recompute (Priority: P2)

An operator upgrades an instance that already holds thousands of placeholder automations. The upgrade removes those automations and records their fingerprints, so after the upgrade Infrahub does not recompute the display labels, HFIDs and computed attributes of every kind on every branch.

**Why this priority**: Without this, the first schema update after the upgrade would treat every template as new and recompute every node of every kind on every diverging branch. On the instances that motivated this work, that is the largest possible load.

**Independent Test**: On an instance that runs the current release with display labels, HFIDs and Jinja2 computed attributes on several kinds and two diverging branches, upgrade, then load the unchanged schema. The placeholder automations are gone and no recompute is submitted.

**Acceptance Scenarios**:

1. **Given** an instance with placeholder automations for display labels, HFIDs and Jinja2 computed attributes, **When** the operator upgrades, **Then** those automations no longer exist in the task manager.
2. **Given** the upgraded instance, **When** the unchanged schema is loaded again, **Then** no display label, HFID or Jinja2 computed attribute recompute is submitted.
3. **Given** the upgraded instance, **When** a template is then changed, **Then** the nodes of that kind are recomputed as described in User Story 2.
4. **Given** an instance where a kind has a template but no placeholder automation (for example because a previous setup run failed), **When** the operator upgrades and the schema is loaded, **Then** that kind is recomputed, as the current release does for a missing automation.

---

### User Story 4 - Branch lifecycle keeps the recorded fingerprints consistent (Priority: P3)

Users create, rebase, merge and delete branches that carry schema changes. The recorded fingerprints follow the branch, so a deleted branch leaves nothing behind and a later branch with the same name starts from a clean state.

**Why this priority**: Recorded fingerprints that outlive their branch grow without bound, which is the problem this work removes, and a stale fingerprint can suppress a recompute on a new branch that reuses the name.

**Independent Test**: Create a branch with a schema change on a kind with a display label, delete the branch, create a branch with the same name and the same change, and check that its nodes are recomputed.

**Acceptance Scenarios**:

1. **Given** a branch with its own recorded fingerprints, **When** the branch is deleted, **Then** its recorded fingerprints are removed.
2. **Given** a deleted branch, **When** a new branch with the same name and a diverging template is created, **Then** the nodes of that kind on the new branch are recomputed.
3. **Given** a branch whose schema no longer differs from the default branch (for example after a rebase that brought the same change), **When** its schema is processed, **Then** its own recorded fingerprints are removed and the default branch fingerprints apply to it, as the automations do today.

### Edge Cases

- Two schema updates on the same branch are processed at the same time: a template change is recomputed at least once and the recorded fingerprint ends up equal to the schema's fingerprint.
- The recompute for a changed template cannot be submitted (task manager unavailable): the fingerprint is not recorded as applied, so the next schema update on that branch submits the recompute again.
- A kind is removed from the schema: its recorded fingerprints are removed and no recompute is submitted for it.
- A template is removed from a kind (the display label or HFID is dropped): its recorded fingerprint is removed. What happens to the stored values of the nodes is unchanged from today.
- The task manager database is reset or replaced while the Infrahub database is kept: the recorded fingerprints remain valid, because they no longer live in the task manager.
- A Jinja2 computed attribute that reads both its own node and a peer: its self-targeting placeholder automation is removed, the recompute after a schema update is decided as today, and the automation that reacts to peer changes remains.
- A branch is deleted while a schema update on that branch is still being processed: no fingerprint is recorded for the deleted branch, so a new branch with the same name is recomputed as in User Story 4.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Infrahub MUST NOT create an automation in the task manager whose only role is to hold the fingerprint of a display label template, an HFID definition or the template of a Jinja2 computed attribute.
- **FR-002**: Infrahub MUST record, in its own database, the fingerprint last applied for each display label template and each HFID definition, per kind and per branch that owns its own definitions. No fingerprint is recorded for Jinja2 computed attributes, because their recompute does not depend on a stored fingerprint.
- **FR-003**: On each schema update, Infrahub MUST compare the display label and HFID fingerprints in the schema with the recorded fingerprints and submit a whole-kind recompute only for the definitions that are new or whose fingerprint differs. Jinja2 computed attributes keep their current recompute decision, which uses the schema and the elements that the schema update changed.
- **FR-004**: Infrahub MUST keep the current branch scoping: the default branch fingerprints apply to every branch whose schema matches the default branch, and a branch whose schema differs owns its fingerprints.
- **FR-005**: Infrahub MUST keep skipping the recompute on a branch when the branch's template for a kind is identical to the default branch template.
- **FR-006**: Infrahub MUST record a fingerprint as applied only after the matching recompute has been submitted, so a failed submission is retried at the next schema update.
- **FR-007**: Concurrent processing of schema updates MUST NOT lose a template change: every change leads to at least one recompute, and the recorded fingerprint ends up equal to the schema's fingerprint.
- **FR-008**: Infrahub MUST remove the recorded fingerprints of a branch when the branch is deleted, when the branch stops owning its own definitions, and when the kind or the template they describe is removed.
- **FR-009**: The upgrade MUST delete the existing placeholder automations of the three families and record the fingerprints that the display label and HFID placeholders hold, so that loading an unchanged schema after the upgrade submits no recompute.
- **FR-010**: The automations that recompute a value when a peer attribute changes MUST keep working as today.
- **FR-011**: The recorded fingerprints MUST NOT be visible or editable through the GraphQL API, the REST API or the web interface.
- **FR-012**: The recompute itself (which nodes are recomputed, how they are grouped into submissions, how merge and rebase recompute changed nodes) MUST stay unchanged.

### Key Entities

- **Recorded template fingerprint**: one record per derived-value family (display label or HFID), per kind, and per branch that owns its own definitions. It holds the fingerprint of the template that was last applied. It is internal to Infrahub, follows the branch it belongs to, and is not part of the user schema.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On an instance with K kinds that define a display label, an HFID or a Jinja2 computed attribute that reads only its own node, and B branches whose schema differs from the default branch, the number of automations in the task manager decreases by the number of placeholder automations the current release creates for that schema (up to K × (B + 1) per family), and does not grow when K or B grows.
- **SC-002**: For a set of schema updates (template added, changed, unchanged, removed, on the default branch and on a diverging branch), no recompute that the current release submits is missing. An extra recompute is allowed only in these cases:
  - after a failed submission;
  - for a branch that came to own its schema during a schema update on another branch, at its next schema update;
  - after the upgrade, for a kind with no placeholder automation to carry over.
- **SC-003**: After upgrading an instance that holds placeholder automations, loading the unchanged schema submits zero recomputes, and the task manager holds zero placeholder automations.
- **SC-004**: After a branch is deleted, zero recorded fingerprints remain for that branch.
- **SC-005**: The time Infrahub takes to process a schema update that changes no template does not increase compared with the current release on the same schema and branch count.

## Assumptions

Nobody could answer questions during this run, so each open point was decided as follows.

- **Scope includes Jinja2 computed attributes.** INFP-441 names display labels and HFIDs only. The epic title is "Refactor placeholder automations", and the Jinja2 computed attributes that read only their own node use the same placeholder pattern (`dev/knowledge/backend/computed-attributes.md`). Leaving them out would keep one third of the placeholder automations, so their placeholder automations are removed. Their recompute decision does not read a stored fingerprint, so no fingerprint is recorded for them.
- **Automations that run stay automations.** Only the automations whose event filter can never match are replaced. The automations that recompute a value when a peer changes, the Python transform computed attribute automations, and the profile refresh automations are out of scope.
- **No change to when or how values are recomputed.** This work changes where the fingerprint is recorded, not the recompute logic. Any improvement to recompute granularity is out of scope.
- **Recorded fingerprints are internal.** INFP-441 says "Users won't notice the change in an observable way aside from seeing lower number of automations in Prefect". The records are therefore not exposed in the API or the web interface, and no schema change visible to users is introduced.
- **The upgrade carries the fingerprints over.** Recording the fingerprints that the existing placeholder automations hold avoids a full recompute after the upgrade. A kind without a placeholder automation is treated as the current release treats it: as a new definition, which is recomputed.
- **The fingerprint is recorded after the recompute is submitted, not after it finishes.** This matches the current release, where the automation is updated before the recompute runs. A recompute that fails while running is handled by the existing retry and failure reporting of recompute flows.
- **The 200-automation display limit of the task manager UI is not addressed directly.** INFP-441 states that the limit becomes an edge case once the automation count no longer grows with the number of kinds and branches.
- **Downgrade is not supported.** Downgrading to a release that expects placeholder automations is out of scope, as for other upgrades that change stored data.
- **Customer naming.** The customer named in INFP-441 is not named in this spec, because the spec is stored in a public repository.
