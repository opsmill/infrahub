# Feature Specification: Auto-create Account Groups from External Authentication Sources

**Feature Branch**: `wvd-20260530-infp-556-spec`
**Created**: 2026-04-30
**Status**: Draft
**Jira/JPD**: [INFP-556](https://opsmill.atlassian.net/browse/INFP-556) — auto-create account groups from external authentication sources
**Related**: [INFP-105](https://opsmill.atlassian.net/browse/INFP-105) (native LDAP support, ship together in 1.10), IFC-2521 (Auto creation of external identity groups epic), IFC-922 (default-group fallback), INFP-474 (login/logout activity events), INFP-536 (account lifecycle — out of scope: removal on claim removal)
**Input**: User description: "I want to create a spec for Jira JPD INFP-556"

## Summary

Enterprise customers manage dozens-to-hundreds of access groups in their external identity providers (Azure AD, Okta, AD behind OIDC, Google Workspace, native LDAP). Today an Infrahub admin must manually pre-create a matching `CoreAccountGroup` for every external group before a logging-in user can be assigned permissions through it; otherwise the claim is silently dropped (or the user falls through to the default group from IFC-922). For customers with hundreds of LDAP-managed groups, this manual pre-provisioning is operationally painful, error-prone, and delays team-by-team onboarding.

This feature delivers opt-in, filter-scoped auto-creation of local Infrahub account groups from claims emitted by external authentication providers (SSO/OIDC, OAuth2, native LDAP), so admins can onboard teams without a manual pre-provisioning step. The feature ships in 1.10 alongside native LDAP support (INFP-105) as one "enterprise identity" story. It hardens an existing community contribution (PR #8515 by Alexander Grooff / Adyen) with the product shaping captured in this spec.

## Clarifications

### Session 2026-04-30

- Q: Should the `source` field on `CoreAccountGroup` record only the kind of origin (`manual` / `system` / `sso`), or also carry IdP identity, and if so under what shape? → A: Enum-only on the group; IdP identity captured on the auto-creation event log entry, not on the group. The enum gains a distinct `ldap` value so native-LDAP-sourced groups are not conflated with SSO/OIDC-sourced groups. Final set: `manual` / `system` / `sso` / `ldap`.
- Q: Should the system bound how many local groups a single login can auto-create, as a guardrail against a misconfigured IdP plus an overly permissive filter? → A: Soft cap (default 50, configurable). Create up to the cap, emit a warning event recording the breach and the dropped claims, login still succeeds. Hard cap is rejected as too aggressive (the user already authenticated). No-cap is rejected as missing belt-and-suspenders defense.
- Q: Should auto-created groups carry a system-seeded description recording their provenance (source IdP, matched pattern, creation date)? → A: No seeded description. Auto-created groups land with an empty description, identical to any other newly-created group. Provenance lives exclusively in the auto-creation event log entry (FR-015). An admin who wants provenance visible on the group is free to add their own description. Rationale: keeps the group entity clean of generated metadata and avoids confusion about whether the seeded text is editable, authoritative, or a substitute for the event log.
- Q: Should the Groups UI ship a dedicated visual indicator and/or filter for `source` in 1.10, or defer entirely? → A: No bespoke UI work in 1.10. `source` is a normal schema attribute on `CoreAccountGroup`, so Infrahub's schema-driven UI auto-renders it as a field/column on the group view and the generic filter mechanism already supports filtering by it — no dedicated work needed. API exposure of `source` is automatic from the same schema definition. Rationale: leverages existing platform behavior; no new UI scope is created in this feature.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Auto-create groups from a filter pattern with name capture (Priority: P1)

As an Infrahub administrator at an enterprise that authenticates via SSO or LDAP, I want to enable filter-scoped auto-creation so that the first time a user logs in whose external identity provider claims contain a group matching my pattern, Infrahub creates the corresponding local `CoreAccountGroup` automatically — with no permissions attached — and adds the user as a member. I no longer have to pre-create local groups one-by-one.

**Why this priority**: This is the core value proposition of the feature. Without it, the customer pain (manual pre-creation of hundreds of groups) is not solved. Every other story is an enhancement, safety net, or auditing layer on top of this primary flow.

**Independent Test**: With auto-creation enabled and a filter such as `^LDAP/group/(?P<name>.+)$`, simulate a login whose claim contains `LDAP/group/network-engineering`. Verify that (a) a `CoreAccountGroup` named `network-engineering` is created with zero attached roles/permissions, (b) the user is added as a member, (c) the new group is tagged with `source = sso`, and (d) on subsequent logins of other users in the same external group, the existing group is reused (no duplicate).

**Acceptance Scenarios**:

1. **Given** auto-creation is enabled and a filter `^LDAP/group/(?P<name>.+)$` is configured, **When** a user logs in whose claim contains `LDAP/group/network-engineering`, **Then** Infrahub creates a local group `network-engineering` with no permissions and adds the user as a member.
2. **Given** the local group `network-engineering` already exists from a prior auto-creation, **When** a different user logs in carrying the same external group, **Then** Infrahub adds the new user to the existing group and does not create a duplicate.
3. **Given** a filter without a named capture group such as `^network-.*$`, **When** a user logs in with claim `network-eng`, **Then** Infrahub creates a group named `network-eng` (full claim used as-is).
4. **Given** an admin attaches a role to an auto-created group, **When** members of that group log in, **Then** they receive the permissions associated with that role through the standard AccountGroup → Role → Permission chain.

---

### User Story 2 - Skip claims that fall outside the filter (Priority: P1)

As an Infrahub administrator, I want only claims that match my configured filter to drive auto-creation, so that unrelated external groups (Slack, GitHub, HR systems, the customer's full corporate directory) do not pollute my Infrahub group list.

**Why this priority**: Without filter scoping, enabling the feature against a real-world IdP that emits hundreds of unrelated group claims per login would flood Infrahub with garbage groups within minutes — a worse outcome than the manual problem the feature is trying to solve. This is what makes the feature safe to enable at all, hence equal priority to Story 1.

**Independent Test**: With filter `^LDAP/group/(?P<name>.+)$` configured, simulate a login carrying both `LDAP/group/network-engineering` and `slack/general` and `github/contributors`. Verify that only `network-engineering` is auto-created and the user is only added to that group; the other claims are ignored. Verify no group named `slack/general` or `github/contributors` appears in the Infrahub group list.

**Acceptance Scenarios**:

1. **Given** a filter `^LDAP/group/(?P<name>.+)$`, **When** a user logs in with claims `LDAP/group/network-engineering`, `slack/general`, `github/contributors`, **Then** only `network-engineering` is auto-created and added; the other claims are silently skipped.
2. **Given** a user has only non-matching claims and no other group assignment exists, **When** they log in, **Then** the user is signed in but receives no group membership through the auto-creation path (the IFC-922 fallback applies if configured — see Story 3).

---

### User Story 3 - Honor the IFC-922 default group when no filter pattern matches (Priority: P2)

As an Infrahub administrator who has configured a `sso_user_default_group` (per IFC-922) for users whose external groups don't match anything I care about, I want auto-creation to coexist with that fallback so users in non-matching claims still land in the default group rather than ending up with no membership at all.

**Why this priority**: Customers who already use the IFC-922 default group rely on it as their "everyone gets at least minimal access" safety net. Breaking that contract would be a regression, but it is independent of and downstream from the core auto-creation behavior, so P2 rather than P1.

**Independent Test**: Configure auto-creation with a filter and configure `sso_user_default_group`. Simulate a login whose claims do not match any filter pattern. Verify the user is added to the configured default group (and not to any auto-created group).

**Acceptance Scenarios**:

1. **Given** auto-creation is enabled, a filter is configured, and `sso_user_default_group` is set, **When** a user logs in with no matching claims, **Then** the user is added to the default group (existing IFC-922 behavior is preserved).
2. **Given** the same configuration, **When** a user logs in with one matching claim and several non-matching claims, **Then** the user is added to the auto-created group from the matching claim; the default group is not added on top (the two paths are independent — matching takes precedence over default).

---

### User Story 4 - Distinguish auto-created groups from manually-created ones (Priority: P2)

As an Infrahub administrator reviewing my groups list, I want to tell at a glance which groups were created manually by me, which are system groups, and which were auto-created from external authentication, so I can audit, attach permissions to the right groups, and trust the provenance of the data.

**Why this priority**: Without this signal, an admin cannot distinguish a deliberately-created group from one auto-spawned by a login flow, making audit and permission attachment harder and more error-prone. Important but secondary to the core behavior; the feature would still function without this property and it can be surfaced in the UI as a follow-up.

**Independent Test**: Trigger auto-creation of a group via a SSO/OIDC login and a separate auto-creation via a native LDAP login. Open the group list (UI and/or API). Verify the SSO-triggered group has `source = sso` and the LDAP-triggered group has `source = ldap`. Manually create a group via the UI/API. Verify it has `source = manual`. Verify existing groups present before the migration are tagged `manual`.

**Acceptance Scenarios**:

1. **Given** a group auto-created from an SSO/OIDC or OAuth2 login, **When** an admin views the group through the API or UI, **Then** the `source` field reads `sso`.
2. **Given** a group auto-created from a native LDAP login, **When** an admin views the group through the API or UI, **Then** the `source` field reads `ldap`.
3. **Given** a manually-created group (via UI, API, or schema load), **When** an admin views it, **Then** the `source` field reads `manual`.
4. **Given** an Infrahub instance upgraded from a pre-feature version, **When** the schema migration runs, **Then** all pre-existing groups are tagged `source = manual` and no group is left without a source value.

---

### User Story 5 - Auditable record of every auto-creation event (Priority: P2)

As an Infrahub administrator or compliance officer, I want a structured event recorded every time a group is auto-created (with the local group name, the matched pattern, the originating IdP, and the triggering user), so I can audit the provenance of every group on the system.

**Why this priority**: Required by enterprise customers for compliance and incident review (e.g., "who or what caused this group to exist?"). Important for trust in the feature but does not block the primary admin or end-user flows from working.

**Independent Test**: With the activity event log open, trigger auto-creation. Verify an event appears containing the new local group name, the source pattern that matched, the IdP identifier, and the username of the user whose login triggered creation.

**Acceptance Scenarios**:

1. **Given** auto-creation is enabled and a login triggers a new group, **When** the event log is queried, **Then** a structured event is present with fields: local group name, source pattern, IdP, triggering user.
2. **Given** the same external group claim arrives on a subsequent login (no creation occurs because the group already exists), **When** the event log is queried, **Then** no auto-creation event is emitted for that login (only the original creation is recorded).

---

### User Story 6 - Refuse to start with an enabled-but-unfiltered configuration (Priority: P3)

As an Infrahub operator, when I enable auto-creation but forget to set a filter, I want Infrahub to refuse to start with a clear configuration error rather than silently auto-creating every group emitted by every IdP — because the resulting cleanup would be worse than a startup failure.

**Why this priority**: A guardrail against an admin mis-configuration. Strongly desired for safety, but the feature is functionally usable with a documentation-only warning; the hard error is the recommended choice but the spec calls it out explicitly because it is one of the explicit open issues from the JPD ticket.

**Independent Test**: Set `INFRAHUB_SECURITY_AUTO_CREATE_GROUPS=true` and leave the filter unset. Start Infrahub. Verify startup fails with a clear error referencing the missing filter.

**Acceptance Scenarios**:

1. **Given** `INFRAHUB_SECURITY_AUTO_CREATE_GROUPS=true` and no filter configured, **When** Infrahub starts, **Then** startup fails with a configuration error that names the missing setting and explains why a filter is mandatory.
2. **Given** the feature is disabled (default), **When** Infrahub starts, **Then** the absence of a filter is not an error and the feature is inactive.

---

### Edge Cases

- **Concurrent first-login**: Two users in the same brand-new external group log in within milliseconds of each other. The system MUST produce exactly one local group, both users MUST be added to it, and neither login MUST fail.
- **Invalid effective name**: A capture group produces a string that is not a valid Infrahub group identifier (empty string, whitespace, characters violating naming rules). The login MUST succeed and the offending claim MUST be skipped with a logged event; no exception MUST surface to the user as a 500.
- **Same effective name from two providers**: Two configured external authentication providers each emit a claim that resolves to the same effective local name. The local group is deduplicated to one. The `source` property of that single group records the originating provider per the assumption below.
- **Misconfigured IdP with hundreds of group claims per login**: The filter is the primary mitigation. As a secondary safeguard, the per-login soft cap (FR-020, default 50) bounds how many new groups a single login can create — claims beyond the cap are dropped for that login with a warning event recorded; the login still completes. The cap applies to *new* group creations only; assignments to already-existing groups are not capped.
- **Invalid regex at config load**: An admin-supplied filter that does not compile MUST cause a startup configuration error that names the setting and the regex error, not a runtime failure on the first login.
- **Filter changed at runtime**: An admin updates the filter and restarts. Already-existing auto-created groups MUST be retained (auto-creation does not delete groups; lifecycle/cleanup is INFP-536, explicitly out of scope).
- **External group renamed in the IdP**: The renamed claim drives a new auto-creation. The old local group remains (no automatic rename). Users who carry only the renamed claim are added to the new group; users still carrying the old claim remain in the old group. (Rename reconciliation is explicitly out of scope.)
- **External group removed from the IdP**: A user no longer carries the claim. The user remains a member of the local group. Removal-on-claim-removal is tracked under INFP-536 and out of scope here.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide an opt-in toggle (`INFRAHUB_SECURITY_AUTO_CREATE_GROUPS`, boolean, default `false`) that controls whether auto-creation runs at all.
- **FR-002**: System MUST require a filter (`INFRAHUB_SECURITY_AUTO_CREATE_GROUPS_FILTER`) when auto-creation is enabled. The filter MUST be either a single regex string or an ordered list of regex strings.
- **FR-003**: System MUST refuse to start (configuration error) when auto-creation is enabled and the filter is unset, empty, or otherwise unusable.
- **FR-004**: System MUST validate every supplied regex pattern at configuration load time (before any login traffic). Invalid regex MUST produce a startup error naming the failing setting and the parse error.
- **FR-005**: System MUST, on every login from an external identity source (SSO/OIDC, OAuth2, native LDAP), evaluate every external group claim against the configured filter(s), in declared order if a list is supplied, and stop at the first match per claim.
- **FR-006**: System MUST, when a claim matches a filter pattern that contains a named capture group `(?P<name>...)`, use the captured value as the local Infrahub group name.
- **FR-007**: System MUST, when a claim matches a filter pattern that has no named capture group, use the full external claim string as-is as the local Infrahub group name.
- **FR-008**: System MUST NOT support index-based capture groups (positional `\1`, `\2`); only named captures are recognized for name extraction. Patterns may still contain unnamed groups for matching purposes — they are simply not used to derive the local name.
- **FR-009**: System MUST, on first encounter of an effective name that has no corresponding local `CoreAccountGroup`, atomically create that group with zero attached roles and zero attached permissions.
- **FR-010**: System MUST, on every encounter of an effective name (first or subsequent), ensure the logging-in user is a member of the corresponding local group.
- **FR-011**: System MUST be safe under concurrency: simultaneous first-logins for the same brand-new effective name MUST result in exactly one local group, and every involved login MUST succeed.
- **FR-012**: System MUST tag every auto-created group with a `source` value that reflects the originating auth flow: `sso` for groups created from an SSO/OIDC or OAuth2 login, `ldap` for groups created from a native LDAP login. The `source` property MUST be modeled as a regular attribute on `CoreAccountGroup` (not as bespoke metadata) so the existing schema-driven UI and API surface it without dedicated UI work — admins can view and filter groups by `source` through the standard group list mechanism. Allowed values: `manual`, `system`, `sso`, `ldap`.
- **FR-013**: System MUST default the `source` of all groups created by routes other than auto-creation to `manual` (UI-created, API-created, schema-loaded). System-internal groups (e.g., bootstrap groups) MUST be tagged `system`.
- **FR-014**: System MUST migrate existing `CoreAccountGroup` rows on upgrade so every group has a non-null `source`; pre-existing groups MUST be set to `manual`.
- **FR-015**: System MUST emit a structured event on every successful auto-creation (creation only, not on subsequent membership additions to an existing auto-created group). The event MUST contain at minimum: the local group name, the regex pattern that matched, an identifier for the originating IdP, and the username of the triggering user.
- **FR-016**: System MUST honor the existing `sso_user_default_group` (IFC-922) when a user's claims produce no matches under the configured filter and a default group is configured. Auto-creation and the default-group fallback MUST be independent: if at least one claim matches, the matching path takes effect; the default group is not stacked on top.
- **FR-017**: System MUST, when a captured/effective name fails Infrahub group identifier validation, skip that claim, complete the login, and emit a logged event recording the rejected claim. No exception MUST propagate to the end user.
- **FR-018**: System MUST deduplicate effective names within a single login (multiple claims that resolve to the same name produce one membership operation, not multiple) and across providers (two providers contributing the same effective name produce one local group, not duplicates).
- **FR-019**: Documentation MUST be updated (`docs/topics/security/sso.mdx`) with a worked example, an explicit safety note about filter scoping, the interaction with the IFC-922 default group, and credit to the contributing customer/author per the assumption below.
- **FR-020**: System MUST enforce a per-login soft cap on the number of new groups auto-creation will produce within a single login (default `50`, configurable via a setting alongside the feature toggle). Up to the cap, auto-creation proceeds normally. When a single login would exceed the cap, the system MUST stop creating groups for that login at the cap, complete the login successfully, and emit a structured warning event recording the cap value, the number of claims dropped, and the dropped claim values (truncated to a reasonable upper bound for log volume).

### Key Entities

- **Account Group (`CoreAccountGroup`)**: An existing Infrahub entity that represents a named group of accounts and acts as the carrier of role/permission assignments. This feature adds a `source` property whose value is one of `manual`, `system`, `sso`, or `ldap`. Existing relationships to Roles, Permissions, and Account members are unchanged.
- **External Group Claim**: A group identifier supplied by an external identity provider as part of the login session. Examples: `LDAP/group/network-engineering`, `azure/network/eng`, a raw LDAP group DN. The shape is provider-specific; the feature treats the claim as an opaque string and matches it against the configured filter.
- **Filter Pattern**: An admin-configured regex (single string or ordered list of strings). Compiled once at config load. Optionally contains a named capture group `(?P<name>...)` to derive the local group name. Without a named capture, the full matched claim string is used.
- **Auto-Creation Event**: A structured record emitted into the Infrahub event/activity log every time auto-creation produces a new local group. Carries: local group name, source pattern, IdP, triggering user, timestamp.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An administrator can onboard a team of N external groups by configuring auto-creation once and letting the first user from each group log in, completing the team's group provisioning without per-group manual UI/API actions. (Operational outcome — the manual pre-creation step is eliminated.)
- **SC-002**: For an enterprise customer with 100+ externally-managed groups, time-to-onboard a new team drops from a manual per-group provisioning task (currently measured in admin-minutes per group) to a zero-action automatic provisioning on first login.
- **SC-003**: When auto-creation is enabled with a typical filter pattern, no group is created from claims that do not match the filter, even if the IdP emits hundreds of unrelated claims per login. (Verified by simulating logins with 100+ unrelated claims and confirming zero unintended groups.)
- **SC-004**: Login latency on the first-encounter login that triggers auto-creation MUST not visibly degrade the user-perceived sign-in experience (the user does not perceive a hang). Subsequent logins reusing the existing group MUST complete with no measurable additional latency vs. baseline (no auto-creation feature) login.
- **SC-005**: 100% of groups auto-created from an SSO/OIDC or OAuth2 login carry `source = sso`, 100% of groups auto-created from a native LDAP login carry `source = ldap`, and 100% of pre-existing groups carry `source = manual` after migration; an audit query that counts groups grouped by `source` returns the expected partition with no nulls.
- **SC-006**: 100% of auto-creation events are recorded in the event log and queryable by IdP, by triggering user, and by the matched pattern, enabling a compliance audit to reconstruct the full creation history of any auto-created group.
- **SC-007**: A misconfiguration (auto-creation enabled, filter missing) is caught at startup with a clear error 100% of the time and never results in unfiltered runtime auto-creation in production.
- **SC-008**: Concurrent first-logins for the same new external group produce exactly one local group across all observed cases (verified under a concurrency test that issues N simultaneous first-logins for the same brand-new external group).

## Assumptions

- **Provider scope**: The feature applies to login flows for SSO (OIDC), OAuth2, OIDC-fronted LDAP/AD, and the native LDAP support landing in 1.10 (INFP-105). All four flows produce a list of external group identifiers per login that this feature treats uniformly.
- **Permissions model unchanged**: The chain `AccountGroup → Role → Permission` is not modified. Auto-created groups land with no roles attached; all permission grants remain a deliberate admin action.
- **`source` recording when two providers contribute the same name** *(resolved 2026-04-30 — see Clarifications)*: The `source` property on the group is enum-only and reflects the kind of originating auth flow (`sso` for OIDC/OAuth2, `ldap` for native LDAP). IdP/server identity is recorded only on the auto-creation event log entry, not on the group itself. If two providers of the same kind contribute the same effective local name, the group is deduplicated and the existing `source` value is retained. If two providers of different kinds (one SSO, one LDAP) ever contribute the same effective local name, the value set at first creation is retained — provenance of any subsequent contributions is captured exclusively in the event log.
- **Per-login creation cap** *(resolved 2026-04-30 — see Clarifications)*: A soft per-login cap is in scope (FR-020), default `50`, configurable. The cap counts only *new* group creations within a single login; membership assignment to already-existing groups is unbounded. When the cap is hit, auto-creation stops for that login, the login still succeeds, and a warning event is emitted. Per-instance/hourly caps are not added — the per-login cap plus the mandatory filter cover the documented misconfiguration risk.
- **Source filter / visual marker in the UI** *(resolved 2026-04-30 — see Clarifications)*: No dedicated UI work is in scope. Because `source` is a regular schema attribute of `CoreAccountGroup` (FR-012), Infrahub's schema-driven UI auto-renders it as a field/column on the group view and the generic filter mechanism already supports filtering by it. The Adyen "nice-to-have" UI request is therefore satisfied by the schema definition itself, with no bespoke UI work.
- **Seeded description on auto-created groups** *(resolved 2026-04-30 — see Clarifications)*: Auto-created groups do not receive a system-seeded description. Provenance is captured exclusively on the auto-creation event log entry (FR-015). The group's `description` field is left empty at creation time and is freely editable by admins like any other group description.
- **Lifecycle / removal**: Removing a user from a local group when the IdP stops sending the claim is explicitly out of scope here and is tracked under INFP-536 (Account Lifecycle Management).
- **Existing PR**: Implementation hardens PR #8515 (Alexander Grooff / Adyen). Release notes credit to Alexander Grooff, wording coordinated with Yvonne — to be finalized at release time.
- **Configuration surface**: Two settings are introduced under the existing `SecuritySettings` configuration area. The exact shape is captured in FR-001 / FR-002 above; the implementation plan owns naming and any internal data-class design.
- **Schema migration**: Adding the `source` property to `CoreAccountGroup` is a non-destructive schema migration that runs as part of the 1.10 upgrade path. The migration seeds `manual` on every pre-existing group.

## Out of Scope

- **Removal of users / groups when external membership changes**: Tracked under INFP-536 (Account Lifecycle Management). This feature only adds members on login; it never removes them, and it never deletes auto-created groups.
- **Renaming local groups when the external claim is renamed**: The local name is derived at first encounter; subsequent renames in the IdP produce a new local group, not a rename of the old one.
- **Bespoke UI components for `source` (custom badges, dedicated filter widgets)**: Not in scope. Display and filtering rely on Infrahub's existing schema-driven UI behavior for regular attributes; no custom rendering work is planned.
- **Per-instance / global rate limit on auto-creation**: A hourly or daily per-instance cap is not implemented. The per-login soft cap (FR-020) plus the mandatory filter are deemed sufficient.
- **Permission/role auto-attachment for auto-created groups**: Out of scope. Every auto-created group lands with zero roles; permissions remain a deliberate admin action.
