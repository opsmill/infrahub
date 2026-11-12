# Feature Specification: Owner and source metadata, and extension points for ownership-based permissions (Community side), storage option B

**Feature Branch**: `rbac-owners-option-b-infp-753`

**Created**: 2026-11-10

**Status**: Draft

**Input**: User description: "INFP-753 Advanced RBAC, Community side, storage option B. Infrahub Community stores and applies owners and node sources, and provides the extension points that Infrahub Enterprise uses to restrict changes by owner. In Community, owners and sources restrict nothing. View is not restricted by owner. Storage option B of the INFP-753 design: `HAS_OWNER` edges from the node vertex, with edge properties for relationship field owners and for owners that a profile or an object template gives, and one shared marker vertex for the own state."

**Source ticket**: [INFP-753, ownership-based permissions and source metadata][INFP-753]. Initiative: [INFP-489, Advanced RBAC][INFP-489].

**Related tickets**: [INFP-477][INFP-477] asks to enforce `is_protected`, which the design replaces. [INFP-478][INFP-478] asks for node-level metadata, and the design uses its owner and source parts.

**Sibling spec**: [`infp-753-rbac-owners-option-e`](../infp-753-rbac-owners-option-e/spec.md) describes the same behaviour with storage option E. The team builds one of the two. The two specs differ only in the section "Storage constraint" and in the requirements, risks and open points that refer to it.

## Summary

- Problem: teams that share one Infrahub instance cannot record which teams own a node. Today a node has no owner, an attribute or a relationship link has one owner at most, and an owner restricts nothing ([design, section 4][design]). Infrahub Enterprise must limit changes to the nodes that a team owns, so it needs the owners first, and it needs a place in each change where it can refuse.
- What the Community side needs:
  - Several owners per node, per attribute and per relationship field, stored separately on each branch, in three states: inherit, own owners, no owner.
  - Owners that apply without a copy: components and children take the owners of their parent, and profiles and object templates give owners to nodes and to fields.
  - An API read of each owner and where it comes from, and a filter by owner and by "no owner".
  - Several sources per node, with a filter by source.
  - The extension points that Infrahub Enterprise uses to restrict changes by owner. In Community, they allow everything that is allowed today.
  - No change in behaviour, permissions or speed for a customer who does not use owners.
- Not part of this spec: all frontend changes. This spec covers the backend: the storage, the GraphQL API, object files, the upgrade and the extension points (section "Out of scope").
- Storage: this spec uses option B of the [engineering design, section 6][eng]. The team did not choose between options B and E on 2026-11-09.
- Not decided yet:
  - Which storage option the team builds: B or E.
  - Product must decide which edition gets the owner and source filters, and the refusals that name the field, the missing permission and the owners ([design, Q-23][design]). This spec puts the filters in Community.
  - Product must decide whether one change in the history of a profile is enough for audits (D-6).
  - Product must confirm the performance limits. The owner filter does not meet SC-003 on the largest kind with either storage option.

## Sources

Where two sources disagree, the later one wins. This spec says so at each point.

1. The product design: [Advanced RBAC: ownership-based permissions and source metadata][design], last edited 2026-10-27. It still describes the view restriction, which is no longer in scope.
2. The engineering design: [INFP-753 Advanced RBAC ownership-based permissions and source metadata][eng], read on 2026-11-09. It holds the behaviour table, the GraphQL shape and the storage options.
3. The grilling sessions of 2026-10-22, 2026-10-27, 2026-11-02, 2026-11-03 and 2026-11-04, the scope change of 2026-11-02, the product meeting of 2026-11-09, and the benchmarks of 2026-11-03 and 2026-11-09. Their notes are on the dev VM (section "Earlier work on the dev VM").
4. The earlier spec sets `infp-489-ownership-phase-1` to `infp-489-ownership-phase-3`, of 2026-10-22 to 2026-10-27. They used storage option A, which is ruled out. This spec replaces them for the Community side.

## Scope: the Community side

- The owner and source metadata is part of Infrahub Community, where it restricts nothing. The permissions are part of Infrahub Enterprise: the "applies to" setting on object permissions, and the action and the global permission for changing owners ([design, section 1][design], decision on editions of 2026-10-22).
- Since 2026-11-02, Infrahub does not restrict view by owner or by field. A user with a view permission on a kind views all nodes of that kind, with all their fields, as today. Lists, counts, search, diffs and the activity log do not change. Ownership restricts only changes. The earlier phase 3 (hide nodes and fields) is dropped.
- This spec covers what Infrahub Community must hold so that Infrahub Enterprise can restrict changes:
  - the owner and source metadata (the earlier phase 1)
  - the extension points for the checks of Infrahub Enterprise (the Community part of the earlier phase 2)
  - the account group tree, because roles are part of Community
- This spec does not cover frontend changes (decision of 2026-11-10). Users view and set owners and sources through GraphQL, the Python SDK and object files. The section "Out of scope" lists the frontend changes that the earlier sources name.
- This spec does not cover the checks themselves. Infrahub Enterprise holds the rule that decides, the ranking of "owned" permissions, the role preset, and the queries that explain a decision.

### Delivery steps

Each step builds on the step before it ([eng, section 1][eng]).

- Step 1 (P1.1): node owners, inheritance and the owner filter. User stories 1 and 5.
- Step 2 (P1.2): owners given by profiles and object templates. User story 2.
- Step 3 (P1.3): owners of single attributes and relationship fields. User story 3.
- Step 4 (P1.4): node sources. User story 4.
- Step 5: the extension points for Infrahub Enterprise. User story 6.
- Step 6: the account group tree behind a setting. User story 7.

The engineering spike measures the checks of Infrahub Enterprise on the storage of step 1 before step 1 is merged.

The step numbers are the numbers of the engineering design. The plan and the tasks follow the priorities of the user stories, so the work on step 5 comes before the work on steps 3 and 4. This order is a proposal of this spec. The tasks file lists what each step needs, so the team can change the order.

## Clarifications

### Sessions of 2026-10-22 and 2026-10-27

- Q: Is the work split between the storage of owners and the enforcement? → A: Yes. Phase 1 stores and applies owners. Phase 2 enforces changes.
- Q: Are inherited owners copied to each node? → A: No. Infrahub reads them (D-1).
- Q: Do the proposed change diff and the activity log show owner names? → A: Yes. A readable field name, and the owners added and removed by display label. Event payloads keep the UUIDs.
- Q: Does the upgrade close repository owners on relationship links? → A: No. It closes them on attributes only. Infrahub refuses repositories as owners everywhere from the upgrade.
- Q: Does the owner metadata go to Community or to Enterprise? → A: Community. The design decided the editions on 2026-10-22.
- Q: Where does the check of Infrahub Enterprise run? → A: Inside the mutation, through a Community "change guard", which this spec names the change check, with an implementation that allows everything. Infrahub Enterprise supplies the implementation that checks.
- Q: Where does "applies to" live? → A: Community defines it. Community refuses to save an Enterprise value, and gives no right to a permission that has one.
- Q: Does the account group tree count for roles? → A: Behind a setting, off by default, in Community.

### Scope change of 2026-11-02

- Q: Does Infrahub restrict view by owner? → A: No. Everyone with a view permission on the kind views the whole node. Ownership restricts only who can change what.

### Sessions of 2026-11-02 to 2026-11-04

- Q: Do owners stay as a list of UUIDs in one metadata attribute (option A)? → A: No. Option A is ruled out. To find the nodes of one owner, Infrahub must read every owner list.
- Q: What matters most for the storage choice? → A: The database structure. A later migration of the structure and the data is heavy. The amount of diff and merge code matters less.
- Q: Can one relationship field have different owners for different links? → A: No. The owners of a relationship field apply to all its links.

### Product meeting of 2026-11-09

- Q: What does the API return for owners? → A: An `ownership` block with the state, the origin, the origin node and the list of owners. Each owner and the origin node give their ID, kind, display label and HFID. The `from_template` field and the `field_owners` output of `node_metadata` are removed.
- Q: How does a mutation name an owner? → A: By ID, or by HFID with the kind.
- Q: Which storage option does the team build? → A: Not decided. The team asked for a benchmark of options B and E. The benchmark of 2026-11-09 did not decide: most reads cost the same.

### Scope decision of 2026-11-10

- Q: Does this spec include frontend changes? → A: No. This spec covers the backend only.

## User Scenarios & Testing *(mandatory)*

All scenarios run through the API: GraphQL, the Python SDK and object files. In a scenario, "shows" means that the API returns the value. No scenario needs a frontend change.

### User Story 1 - A platform team gives owners to many devices, and anyone filters by owner (Priority: P1)

A platform team gives an owner to 1,000 devices. The interfaces of those devices take the owners of their device, so the team does not set owners on 48,000 interfaces. Engineers and auditors then filter devices and interfaces by owner, and find the nodes that nobody owns. The team checks the owners before Infrahub Enterprise starts to enforce them.

**Why this priority**: a customer must give owners and check them before enforcement exists. All other stories need stored owners, inheritance through parents and the owner filter.

**Independent Test**: on a data set of 3,000 devices with 48 interfaces each, set owners on 1,000 devices, then filter by owner and by "no owner". Compare the counts and the owners that the API returns with the expected values.

**Acceptance Scenarios**:

1. **Given** 3,000 devices without owners, each with 48 interfaces, **When** the platform team gives `dc-emea` as the owner of 1,000 devices, **Then** a filter on owner `dc-emea` returns those 1,000 devices and their 48,000 interfaces, and each interface shows the owner `dc-emea` with the origin "parent" and the device as origin node.
2. **Given** the same data, **When** an engineer filters devices with the "no owner" filter, **Then** the list returns the other 2,000 devices with the correct count.
3. **Given** a device owned by `dc-emea` and `dc-security`, **When** an auditor filters devices by the owners `dc-emea` or `dc-security`, **Then** the query returns the device one time, with both owners.
4. **Given** a country owned by `network-emea` in a location hierarchy, and a site under that country without own owners, **When** an engineer views the site, **Then** the site shows `network-emea` with the origin "parent" and the country as origin node.
5. **Given** a node whose Parent relationship peer and hierarchy parent have different owners, **When** an engineer views the node, **Then** the node shows the owners of its Parent relationship peer.
6. **Given** an interface whose device has owners, **When** an engineer sets the interface to "no owner", **Then** the interface shows no owner and matches the "no owner" filter.
7. **Given** an interface set to "no owner", **When** an engineer sets the interface back to inherit, **Then** the interface shows the owners of its device again.
8. **Given** a device owned only by the account group `dc-emea`, **When** an administrator deletes `dc-emea`, **Then** the device shows "deleted group", and the device and its interfaces match the "no owner" filter.
9. **Given** the same deleted group, **When** an administrator creates a new account group with the name `dc-emea`, **Then** the device still shows "deleted group", and the new group does not own the device.
10. **Given** a branch, **When** an engineer sets two owners on a device on that branch, **Then** the default branch shows no owners for the device. After the merge, the default branch shows both owners, and the interfaces of the device show them as inherited.
11. **Given** a branch that deletes the account group `dc-emea`, **When** the branch is merged, **Then** a device that `dc-emea` owned shows "deleted group" on the default branch.
12. **Given** a repository, **When** an engineer gives the repository as the owner of a device, **Then** Infrahub refuses the whole change with an error that says that only an account or an account group can be an owner.
13. **Given** a user without view permission on accounts and account groups, **When** the user views a node, **Then** the user views its owners.
14. **Given** a user with update permission on the device kind, **When** the user changes the owners of a device that another team owns, **Then** Infrahub Community stores the change, because owners restrict nothing in Community.

---

### User Story 2 - Profiles and object templates give owners to many nodes (Priority: P2)

A platform team gives owners through a profile that thousands of devices use, or through an object template. A change to the owners that the profile gives reaches every device at the next read, and only the profile records the change.

**Why this priority**: profiles keep the owners of thousands of nodes current without a change on each node ([design, section 6.4][design]). This story needs the storage and the API read of story 1.

**Independent Test**: attach a profile that gives an owner to 3,000 devices. Change the owners that the profile gives, then read the devices, the diff and the activity log. Create a device from an object template, attach a profile, and read the owners of the device.

**Acceptance Scenarios**:

1. **Given** the profile "EMEA fabric devices" gives the owner `dc-emea` and 3,000 devices use it, **When** the platform team adds `dc-security` to the owners that the profile gives, **Then** the next read of any of those devices shows both owners with the origin "profile" and the profile as origin node, and the history of the profile records one change.
2. **Given** the same profile change on a branch, **When** an engineer opens the diff of the branch, **Then** the diff lists one node: the profile.
3. **Given** the template "EMEA leaf" gives the owner `dc-emea`, **When** an engineer creates a device from it, **Then** the device shows `dc-emea` with the origin "template" and the template as origin node.
4. **Given** that device, **When** an engineer later attaches the profile "Security devices" that gives `dc-security`, **Then** the device shows `dc-security` from the profile, because a profile replaces owners that came from a template.
5. **Given** a device created from the template "EMEA leaf", **When** the platform team changes the owners that the template gives, **Then** the device keeps the owners it got at creation.
6. **Given** a device template with interface subtemplates that give owners, **When** an engineer creates a device from the template, **Then** each interface shows the owners that its subtemplate gives.
7. **Given** a device with owners from a profile and from a template, **When** an engineer sets owners directly on the device, **Then** the device shows only the owners set directly.
8. **Given** a device that uses two profiles that give different owners, **When** an engineer views the device, **Then** the device shows the owners of the profile with the higher priority.
9. **Given** a device set directly to "no owner", **When** the platform team attaches a profile that gives owners, **Then** the device still shows no owner.
10. **Given** a profile that gives owners and has its own owners, **When** an engineer changes the own owners of the profile, **Then** the nodes that use the profile do not change.
11. **Given** a profile is removed from a node, **When** an engineer views the node, **Then** the node shows the owners of the next level: its object template, or else its parent.

---

### User Story 3 - A field has its own owners, or no owner (Priority: P3)

A team is responsible for one field of nodes that another team manages. For example, the network team is responsible for the IP addresses of servers, and the server team for the rest of each server. An engineer gives that field its own owners, or sets it to no owner. A profile or an object template can also give owners to that field on many nodes. The other fields keep the owners of the node. Clients that read the `owner` field of today keep working.

**Why this priority**: the design describes this use case as a product use case, not a customer statement ([design, section 2][design]). Stories 1 and 2 cover the needs that customers named.

**Independent Test**: on one server, give own owners to a relationship field without peers, set an attribute to no owner, and reset a field to inherit. Attach a profile that gives owners to one field, and create a server from an object template that gives owners to one field. Read each field in GraphQL and through the `owner` field of today.

**Acceptance Scenarios**:

1. **Given** server `srv01` is owned by `server-team`, and its `ip_addresses` relationship has no peers, **When** an engineer sets the own owners of `ip_addresses` to `network-team`, **Then** `ip_addresses` shows `network-team` with the origin "self", and every other field shows `server-team` with the origin "node".
2. **Given** the same server, **When** an engineer sets the `description` attribute to no owner, **Then** `description` shows no owner, and the other fields keep their owners.
3. **Given** `ip_addresses` has its own owners, **When** an engineer sets the field back to inherit, **Then** `ip_addresses` shows `server-team` with the origin "node" again.
4. **Given** a relationship with 48 peers and its own owners, **When** a client reads the owners of the relationship, **Then** the client gets one `ownership` block for the field, and the same owners apply to all 48 links.
5. **Given** an attribute with exactly one own owner, **When** a client reads the `owner` field of today, **Then** the client gets that owner.
6. **Given** an attribute with two own owners, **When** a client reads the `owner` field of today, **Then** the client gets null.
7. **Given** an attribute with two own owners, **When** a client writes one account group to the `owner` field of today, **Then** the own owners of the attribute become that account group.
8. **Given** a relationship whose links have owners, **When** a client reads `properties { owner }` on the links, **Then** the client gets the same result as before the upgrade, and the owners of the relationship field do not change.
9. **Given** the profile "Server ownership" gives the owner `network-team` to the `ip_addresses` field, **When** the platform team attaches the profile to `srv01`, **Then** `ip_addresses` shows `network-team` with the origin "profile", and the other fields keep the owners of the node.
10. **Given** an object template that gives the owner `network-team` to the `ip_addresses` field, **When** an engineer creates a server from the template, **Then** `ip_addresses` shows `network-team` with the origin "template".
11. **Given** `ip_addresses` of `srv01` has owners set directly on the field, **When** the platform team attaches a profile that gives other owners to `ip_addresses`, **Then** the field keeps the owners set directly.

---

### User Story 4 - Nodes record their sources (Priority: P4)

Teams that load data from other systems record the system that each node comes from, and list the nodes from that system. A source records where the data of a node comes from. It is separate from the owners, and no permission reads it.

**Why this priority**: [INFP-478][INFP-478] asks for object-level source metadata. This story does not depend on stories 2 and 3.

**Independent Test**: create devices with a source, filter devices by that source, and compare the count and the sources that the API returns with the expected values.

**Acceptance Scenarios**:

1. **Given** Infrahub Sync creates 2,000 devices with the source `cmdb-sync`, **When** an engineer filters devices by the source `cmdb-sync`, **Then** the list returns those 2,000 devices with the correct count.
2. **Given** a device with the sources `cmdb-sync` and the repository `infra-data`, **When** an engineer filters devices by `infra-data`, **Then** the list includes the device.
3. **Given** a user with update permission on the device kind, **When** the user changes the sources of a device, **Then** Infrahub stores the new sources, and the activity log records the old and new values.
4. **Given** a device with two sources, **When** a client reads the sources of the device in a list query, **Then** the client gets both sources.
5. **Given** an attribute whose value a profile sets, **When** a client reads the source of the attribute, **Then** the client gets the profile, as before this feature.

---

### User Story 5 - Existing data, clients and speed stay the same after the upgrade (Priority: P1)

Before the upgrade, an administrator runs a report that lists the data whose meaning changes. After the upgrade, existing queries return the same results for existing data. A customer who does not use owners views no change in behaviour or speed.

**Why this priority**: every customer upgrades, including the customers who do not use owners. Story 1 cannot be released without this story.

**Independent Test**: run the report on a fixture that contains each listed case. Upgrade the fixture, then run the existing tests and the query benchmarks.

**Acceptance Scenarios**:

1. **Given** a database with a repository that owns an attribute, a relationship whose links have owners, and a value with `is_protected` set, **When** the administrator runs the report before the upgrade, **Then** the report lists all three.
2. **Given** an attribute owned by a repository, **When** the upgrade runs, **Then** the attribute no longer has the repository as owner, and a query at a time before the upgrade still shows the repository as its owner.
3. **Given** an attribute owned by an account group before the upgrade, **When** a client reads `owner` after the upgrade, **Then** the client gets the same account group, and the `ownership` block of the attribute shows the state "owners" with that group.
4. **Given** an attribute without an owner before the upgrade, **When** a client reads its `ownership` block after the upgrade, **Then** the state is inherit.
5. **Given** an attribute owner written on a branch before the upgrade, **When** a client reads the attribute on that branch after the upgrade, **Then** the client gets the owner of the branch, not the owner of the default branch.
6. **Given** a client that reads `is_protected` or filters by it, **When** the client runs its query after the upgrade, **Then** the client gets the same results, and the schema marks the field and the filter as deprecated.
7. **Given** a customer that has no owners, **When** users run list queries, create, update and delete nodes, load object files and run generators, **Then** the time of each stays within the limits of SC-001 and SC-002.
8. **Given** existing roles and permissions, **When** the upgrade runs, **Then** every user can do exactly what the user could do before.

---

### User Story 6 - Infrahub Enterprise restricts changes by owner, and Infrahub Community restricts nothing (Priority: P2)

A customer on Infrahub Enterprise limits changes to the teams that own a node. Infrahub Enterprise needs one place in every change where it gets the nodes, the action and the fields that change, and where it can refuse the whole change with a clear reason. A customer on Infrahub Community views owners, and no change is refused because of them.

**Why this priority**: the customer need that started this work is to limit changes to owners. Infrahub Enterprise cannot build that check without these extension points. This story needs the owners of story 1.

**Independent Test**: on Infrahub Community, run each kind of change on a node that another team owns, and confirm that Infrahub stores it. Then run the same changes with a test implementation of the change check that refuses one field, and confirm that nothing is written and that the response lists each refused item.

**Acceptance Scenarios**:

1. **Given** Infrahub Community and a device owned by `network-na`, **When** a member of `network-emea` with update permission on devices updates, deletes or changes a relationship of the device, **Then** Infrahub stores the change.
2. **Given** a change check that refuses the `ip_addresses` field, **When** a user changes the name and `ip_addresses` of a server in one mutation, **Then** nothing is written, and the response lists `ip_addresses` as refused with the reason that the check gave.
3. **Given** a change check that refuses two fields, **When** a user changes both in one mutation, **Then** the response lists both refused fields at once.
4. **Given** a request with two mutations and a change check that refuses the first, **When** the request runs, **Then** the second mutation still runs.
5. **Given** a change made from the peer side of a relationship, **When** the mutation runs, **Then** the change check receives both ends of the link and the field on each end.
6. **Given** a delete that cascades to other nodes, **When** the mutation runs, **Then** the change check receives every node that the cascade removes, before anything is deleted.
7. **Given** a create with a profile and an object template, **When** the mutation runs, **Then** the change check receives the node with the owners that apply after the creation, before the create is committed.
8. **Given** a site rename that recomputes the names of devices, **When** the rename runs, **Then** the change check receives the site only, not the devices.
9. **Given** Infrahub Community, **When** an administrator saves an object permission that applies to "owned nodes", or that grants the action for changing owners, **Then** Infrahub refuses it with a message that says that the value needs Infrahub Enterprise.
10. **Given** Infrahub Community and an object permission in the database that applies to "owned nodes", **When** a user who has only that permission changes a node, **Then** Infrahub refuses the change, because the permission gives no right.
11. **Given** a list query that asks for the permissions of the user on each node, **When** the query runs on Infrahub Community, **Then** each node reports the same decision as the kind, as today.

---

### User Story 7 - A member of a subgroup gets the roles of its parent groups (Priority: P3)

A customer keeps its teams as a tree of account groups, for example `dc-emea` with the subgroup `dc-emea-fra`. An administrator turns on a setting so that a member of a subgroup counts as a member of every group above it. Before that, a report lists the users who gain roles.

**Why this priority**: the design asks that group membership includes subgroups, for roles and for owners ([design, section 6.1][design]). Customers can use owners without it. It is off by default so that existing permissions do not change at the upgrade.

**Independent Test**: build a group tree with a role on the parent group. Run the report, turn the setting on, and compare what a member of the subgroup can do before and after.

**Acceptance Scenarios**:

1. **Given** the setting is off and `dc-emea-fra` is a subgroup of `dc-emea`, **When** a member of `dc-emea-fra` only uses a permission that a role of `dc-emea` gives, **Then** Infrahub refuses, as today.
2. **Given** the setting is on, **When** the same user uses that permission, **Then** Infrahub allows it.
3. **Given** the setting is on, **When** a member of `dc-emea` only uses a permission that a role of `dc-emea-fra` gives, **Then** Infrahub refuses, because membership counts downward only.
4. **Given** a parent group with a role and a subgroup with members, **When** an administrator runs the report before turning the setting on, **Then** the report lists the users who gain roles, and the roles.
5. **Given** the setting is on, **When** an administrator moves a subgroup to another parent, **Then** the change takes effect at the next request of each user.

---

### Edge Cases

- E-1: a deleted owner stays in the list as "deleted group". It does not count as an owner. A new group with the same name does not get the data back.
- E-2: a node with both a Parent relationship and a hierarchy parent inherits through the Parent relationship.
- E-3: a component moved to another parent on a branch gets the owners of the new parent. Only the relationship change appears in the diff. Infrahub Enterprise treats the move as an owner change when the owners that apply change.
- E-4: a change to the owners of a device sends an event for the device only. Webhook consumers get no event for its interfaces.
- E-5: an old client reads `owner = null` on a field that has two owners. The deprecation note and the release notes say this.
- E-6: a "no owner" state set directly on a node takes priority over profile owners and parent owners.
- E-7: a profile or an object template has its own owners, separate from the owners it gives to nodes. A change to its own owners does not change the nodes that use it.
- E-8: when a profile is removed from a node, the node shows the owners of the next level in the order of D-6. A field that got owners from the profile goes to the next level of its own order in the same way.
- E-9: a branch-agnostic node keeps its owners on all branches, like its other data.
- E-10: only the Parent relationship and the hierarchy parent pass owners down. A site and the devices in it each keep their own owners, because other relationship kinds pass no owners.
- E-11: a node deleted on a branch loses its owners on the default branch at the merge. No owner data of the deleted node stays active.
- E-12: two branches set the first owners of the same relationship field of the same node. After both merges, the field has one owner state.
- E-13: a node changes kind, through a schema change or an object conversion. The node, its attributes and its relationship fields keep their owners.
- E-14: a schema change renames a field that has owners. The owners follow the field. A schema change removes a field. Its owners are removed.
- E-15: a field takes the owners of its node, and the node takes its owners from a profile. The field shows the origin "node" and its own node as origin node, not the profile ([eng, open points for the GraphQL shape][eng]).
- E-16: a node has more parents above it than the depth limit of the walk to the parents. The option E prototype stops the walk at 16 parents, and then returns no inherited owner. No source sets the limit or the result (section "Open questions").

## Requirements *(mandatory)*

### Decisions that the requirements refer to

The numbers D-1 to D-11 are the numbers of the earlier phase 1 spec. The engineering design uses other numbers in some places. Each decision names its source.

- D-1: Infrahub reads inherited owners. It does not copy them. Only the node whose owners change records a change. Source: session of 2026-10-22.
- D-2: several owners per item. The `owner` field of today is deprecated. On read, it returns the own owner of the field if the field has exactly one, otherwise null. On write, it replaces the own owners of the field. Source: session of 2026-10-22, [eng, section 2][eng].
- D-3: owners pass down through two links only: the Parent relationship and the hierarchy parent. Own owners stop the read. If a node has both links, the Parent relationship wins. Source: session of 2026-10-22.
- D-4: only accounts and account groups can own. From the upgrade, Infrahub refuses any other kind as owner, on links too. The upgrade closes the owner edges from attributes to repositories and deletes nothing. Owners on links stay as they are. A report before the upgrade lists those owners. Source: sessions of 2026-10-22 and 2026-10-27.
- D-5: nodes and fields have three owner states: inherit, own owners and no owner. In a mutation and in an object file: a key left out changes nothing, a list gives own owners, `[]` gives no owner, and `null` gives inherit. Source: session of 2026-10-22, [eng, section 2][eng].
- D-6: Infrahub reads the owners that a profile gives through the profile. The order of owners for a node: its own state, then its profiles by priority, then its object template, then its parent. The history of the profile records a change, not the history of each node. Product decides whether this is enough for audits. Source: session of 2026-10-22, [eng, section 1][eng].
- D-7: object templates copy owners at creation. The copy keeps the origin "template" and the template as origin node. A profile replaces these owners. A direct change replaces both. Later changes to the template do not reach existing nodes. Source: session of 2026-10-22.
- D-8: the owners of a relationship field belong to the node, with one owner state per field. They exist when the field has no peers, and they apply to all links of the field. Source: session of 2026-10-22, [eng, section 6][eng].
- D-9: owners on links stay unchanged as data. No check reads them. `properties { owner }` keeps its meaning of today. The upgrade does not convert them. Source: session of 2026-10-22.
- D-10: sources are on nodes only in this work. Field sources stay as they are today. Anyone with update permission on the kind can change sources. Source: session of 2026-10-22.
- D-11: a read of owners and sources needs no view permission on accounts or account groups, as for `owner` today. Source: session of 2026-10-22, [eng, section 2][eng].
- D-12: Infrahub does not restrict view by owner or by field. Source: scope change of 2026-11-02.
- D-13: the check of Infrahub Enterprise runs inside the mutation, through a Community change check. Changes that follow from the change of a user do not call it. Source: session of 2026-10-27 (H-2).
- D-14: Community defines the "applies to" setting, the action for changing owners and the global permission to manage ownership. Community refuses to save them, and gives no right to a permission that has them. Source: session of 2026-10-27 (H-10).
- D-15: the account group tree counts behind a setting, off by default, in Community. Source: session of 2026-10-27 (H-17).

### Functional Requirements

The names of fields, filters and object file keys in this section follow the [engineering design, section 2][eng]. Product did not sign off on the GraphQL shape. An API review with the frontend and SDK maintainers fixes the names before the SDK change.

#### Store and apply owners

- **FR-001**: Infrahub MUST store several own owners per node, per attribute and per relationship field, separately on each branch.
  - Check: set two owners on a branch. The default branch shows none. After the merge, it shows both.
- **FR-002**: Each node, attribute and relationship field MUST have one of three owner states: inherit, own owners or no owner (D-5).
  - Check: set each state on a node and on a field, and read it back.
- **FR-003**: Infrahub MUST accept only an account or an account group as owner. It MUST refuse the whole mutation, and change nothing, when an owner is not found, is of another kind, is of an unknown kind, has neither an ID nor a kind with an HFID, or has an HFID of the wrong length ([eng, "Errors when an owner is not valid"][eng]).
  - Check: one test for each of the five cases. A repository given as owner is refused.
- **FR-004**: Infrahub MUST resolve the owners of a node in the order of D-6, through the links of D-3.
  - Check: one test for each level of the order, and one for a node with both a Parent relationship and a hierarchy parent.
- **FR-005**: Infrahub MUST resolve the owners of a field in this order: the own state of the field, the owners that its profiles give to the field by profile priority, the owners that its object template gave to the field, then the owners of its node.
  - Check: one test for each level of the order.
- **FR-006**: When the owners of a node or the owners that a profile gives change, only that node or profile MUST record the change. The nodes that inherit MUST show the new owners at the next read (D-1).
  - Check: change the owners of a device. The diff lists one node, and the interfaces show the new owners.
- **FR-007**: The owners of a relationship field MUST belong to the node, MUST exist when the field has no peers, and MUST apply to all links of the field (D-8). Owners on links MUST stay unchanged (D-9).
  - Check: set owners on a relationship without peers, add peers, and read `properties { owner }` on the links.
- **FR-008**: A deleted owner MUST show as deleted and MUST NOT count as an owner. This MUST hold when the owner is deleted on the default branch, and when it is deleted on a branch that is then merged ([eng, section 2][eng]).
  - Check: delete an account group on a branch, merge, and read a node that it owned. The node shows "deleted group" and matches the "no owner" filter.
- **FR-009**: A query that does not request owners and does not filter by owner MUST NOT read owners.
  - Check: a query benchmark shows the same plan and time as before.

#### Read and set owners through the API

- **FR-010**: Users MUST be able to read an `ownership` block on a node, on each attribute and on each relationship field. The block MUST give the state (`OWNERS`, `NO_OWNER`, `INHERIT`), the origin (`SELF`, `PROFILE`, `TEMPLATE`, `PARENT`, `OBJECT`), the origin node, and the owners that apply. The origin node and each owner MUST give their ID, kind, display label and HFID. Each owner MUST say whether it is deleted.
  - Check: the examples of [eng, section 2][eng] return the documented responses.
- **FR-011**: Infrahub MUST return the `ownership` block of a relationship also when the relationship has no peer. For a relationship with several peers, it MUST read the owners of the field once, not once for each peer. When a query asks only for the `ownership` of a relationship, Infrahub MUST NOT read the peers.
  - Check: count the database queries of a page of 50 devices with the `ownership` of `interfaces`.
- **FR-012**: On a profile or an object template, users MUST be able to read the owners that it gives to its nodes and to each field of its nodes, separately from its own owners (E-7).
  - Check: read `target_ownership` and `target_field_ownership` on a profile that gives owners to its nodes and to one field.
- **FR-013**: Users MUST be able to set owners in the create, update and upsert mutations, with the values of D-5: on the node, on an attribute or a relationship field by name, on an attribute next to its value, and, on a profile or an object template, the owners that it gives. A mutation MUST accept each owner by ID, or by HFID with the kind.
  - Check: the mutation examples of [eng, section 2][eng].
- **FR-014**: The `owner` field of today on attributes MUST return the own owner of the field when the field has exactly one own owner, and null in all other cases. A write to it MUST replace the own owners of the field. The field MUST be marked as deprecated (D-2).
  - Check: read and write the field on attributes with zero, one and two own owners.
- **FR-015**: Existing queries that read `owner` on attributes and `properties { owner }` on links MUST return the same results as before for existing data.
  - Check: the existing tests pass without changes.
- **FR-016**: Users MUST be able to read the owners and sources of a node without view permission on accounts or account groups (D-11).
  - Check: a user without that permission reads the owners and sources of a node.
- **FR-017**: Infrahub MUST give one read of the owners that apply to many nodes and fields at one time, so that a page of a list, and a check of Infrahub Enterprise, each run a fixed number of owner queries.
  - Check: the number of owner queries for a page of 50 and for a page of 500 is the same.

#### Find nodes by owner

- **FR-018**: Users MUST be able to filter list queries by one or more owners, in GraphQL. A node matches if any of the owners that apply to it matches, own or inherited. The filter takes IDs.
  - Check: filter interfaces by the owner of their device.
- **FR-019**: Users MUST be able to filter for nodes with no active owner. The filter MUST return the nodes without owners and the nodes whose owners are all deleted.
  - Check: delete an account group. Its nodes match the filter.
- **FR-020**: Infrahub MUST apply the owner and source filters before pagination.
  - Check: the count and the pages are correct on the reference data set.

#### Requirement numbers that this spec does not use

- FR-021 to FR-024 and FR-050 are not used. They held frontend changes, which are not part of this spec (section "Out of scope"). The other numbers do not change, so earlier references stay valid.

#### Owners from profiles, object templates and object files

- **FR-025**: A profile MUST be able to give owners to its nodes and to single fields of its nodes. Infrahub MUST read these owners through the profile, by profile priority (D-6).
  - Check: user story 2, scenarios 1, 8 and 9. User story 3, scenario 9.
- **FR-026**: When a node is created from an object template, Infrahub MUST copy the owners that the template gives to the node and to its fields, and the owners that each subtemplate gives to its component. The copy MUST keep the origin "template". Later changes to the template MUST NOT change existing nodes (D-7).
  - Check: create a device from a template with interface subtemplates, change the owners of the template, and read the device, its fields and its interfaces.
- **FR-027**: The creation of a node from an object template MUST read the owners of the template and of its subtemplates a fixed number of times, not once for each component.
  - Check: the number of owner reads is the same for a template with 2 components and with 6 components.
- **FR-028**: Object files MUST set the owners and sources of a node under `node_metadata`, and the owners of a field on the field, with the values of D-5.
  - A plain name is an account group. An account uses a typed form with its kind. Infrahub refuses a name that matches both an account and an account group.
  - In a profile or an object template, `node_metadata` also sets the owners that it gives to its nodes. A field can carry owners without a value.
  - Check: load files with each form and compare the stored states.

#### Owners on branches

- **FR-029**: The diff of a branch and of a proposed change MUST include changes to owners and owner states on nodes and fields, and changes to node sources. Each change MUST give a readable field name and the owners added and removed, by display label. A deleted owner MUST be marked as deleted.
  - Check: add an owner on a branch. The diff query returns the display label of the added owner, not its UUID.
- **FR-030**: A merge and a rebase MUST carry the owners of nodes, of fields and of the sets that profiles and object templates give. Conflict detection MUST report a conflict when the default branch and another branch change the owner state of the same item, and the two changes cannot both apply. The rule that says which pairs of changes cannot both apply is not decided (section "Open questions"). The option E prototype reports a conflict when both sides change the owners of the same item to different lists.
  - Check: one scenario test for each of these cases, with a read on the branch, in the diff and on the default branch after the merge: owners set, an owner added, an owner removed, "no owner" set, a node deleted on the branch, a rebase after both sides changed the same owners, two branches merged one after the other, a profile changed on a branch, a parent changed on a branch.
- **FR-031**: The activity log MUST record changes to owners and sources, with the old and new values. The activity log query MUST return the owners by display label, resolved when the log is read.
  - Check: an event test, and a read of the activity log after a rename of the owner group.
- **FR-032**: When two writes of owners or sources on the same item run at the same time, Infrahub MUST keep one owner state for the item. The state MUST be the complete state of one of the writes, and never a mix of both.
  - On one branch, the writes MUST apply one after the other, so the state of the last write stays.
  - On two branches, the item MUST have one owner state after both merges. FR-030 says whether the second merge reports a conflict.
  - A mutation replaces the whole list of owners of an item (D-5), so two writes at the same time cannot both stay. "The state of the last write stays" is a proposal of this spec. No source sets it.
  - Check: run two first writes of owners on one node at the same time, and merge two branches that each set the first owners of the same field.
- **FR-053**: A change of the owners or of the sources of a node MUST update the "updated at" and "updated by" metadata of that node, like a change of a value. The nodes that inherit MUST NOT get new metadata (D-1). This requirement is a proposal of this spec. No source sets it.
  - Check: change only the owners of a device. Read `node_metadata { updated_at updated_by }` on the device and on one of its interfaces.

#### Node sources

- **FR-033**: Infrahub MUST store several sources per node, separately on each branch. A source can be an account, an account group, a repository, a resource pool, a profile or an object template. Users with update permission on the kind MUST be able to change them (D-10).
  - Check: set two sources on a branch. The default branch shows none. After the merge, it shows both.
- **FR-034**: Users MUST be able to filter list queries by one or more sources, in GraphQL. A node matches if any of its sources matches.
  - Check: the filter on the source `cmdb-sync` returns 2,000 devices with the correct count.
- **FR-035**: The sources of attributes and relationships MUST stay as they are today (D-10).
  - Check: the existing tests pass without changes.

#### Upgrade and schema changes

- **FR-036**: From the time of the upgrade, Infrahub MUST refuse repositories as owners. The upgrade MUST close the owner edges from attributes to repositories and delete no data, so queries at a time before the upgrade still show the repositories as owners. Owners on links MUST stay as they are (D-4).
  - Check: a migration test on a fixture with repository owners, account group owners and attributes without owners.
- **FR-037**: After the upgrade, each existing attribute owner MUST read as the own state with that one owner, on the branch where it was written. An attribute without an owner MUST read as inherit.
  - Check: user story 5, scenarios 3 to 5.
- **FR-038**: A report available before the upgrade MUST list the repository owners, the relationships whose links have owners, and the values with `is_protected` set.
  - Check: run the report on a fixture that contains each case.
- **FR-039**: `is_protected` and its filter MUST be marked as deprecated. Their behaviour MUST NOT change.
  - Check: a test of the schema and of the existing behaviour.
- **FR-040**: The owners of a node, of its attributes and of its relationship fields MUST follow the node when its kind changes, through a schema change or an object conversion. The owners that a profile or an object template gives MUST follow it in the same way.
  - Check: change the kind of a node whose node owners and `interfaces` field owners include the same account group. Both owner states are complete after the change.
- **FR-041**: The owners of a field MUST follow the field when a schema change renames it, and MUST be removed when a schema change removes it. This covers the own owners of the field on each node, and the owners that profiles and object templates give to the field.
  - Check: rename and remove an attribute and a relationship that have owners, on the default branch and on a branch that is then merged.

#### Extension points for Infrahub Enterprise

- **FR-042**: Infrahub Community MUST define one change check that the create, update, upsert and delete mutations, and the mutations that add and remove relationship peers, call inside their transaction. The call MUST come when the mutation knows the nodes, the action and the fields that change, both ends of each link included, and before the transaction commits (D-13).
  - Check: a test implementation records the calls of each mutation kind, with a change made from the peer side.
- **FR-043**: The Community implementation of the change check MUST allow everything that the permissions of today allow, and MUST NOT read owners.
  - Check: count the database queries of a mutation before and after this work. User story 6, scenario 1.
- **FR-044**: The change check MUST receive, for a create, the node with the owners that apply after the creation. For a delete, it MUST receive every node that the cascade removes. For a change of parent, it MUST receive the old and the new parent.
  - Check: user story 6, scenarios 6 and 7.
- **FR-045**: When the change check refuses, the mutation MUST write nothing. The response MUST list every refused node, field or side of a link at once, with the reason that the check gave for each. Other mutations of the same request MUST still run. An object file load MUST stop at the refused node.
  - Check: user story 6, scenarios 2 to 4.
- **FR-046**: Changes that follow from the change of a user MUST NOT call the change check: profile values applied to nodes, computed attributes, the components that an object template creates, resource pool allocations, and merges (D-13).
  - Check: user story 6, scenario 8. A device template with 48 interfaces creates all of them with one call.
- **FR-047**: Object permissions MUST have an "applies to" setting with three values: all nodes, owned nodes, nodes without owners. "All nodes" MUST be the default, and existing permissions MUST get it. Infrahub MUST also define an action for changing owners, which the `any` action does not include, and a global permission to manage ownership (D-14).
  - Check: an upgrade test, and the existing permission tests pass without changes.
- **FR-048**: Infrahub Community MUST refuse to save an object permission whose "applies to" is not "all nodes", or that grants the action for changing owners, and MUST refuse to grant the global permission to manage ownership. The message MUST say that the value needs Infrahub Enterprise. If such a permission exists in the database, Infrahub Community MUST give it no right (D-14).
  - Check: user story 6, scenarios 9 and 10.
- **FR-049**: Users MUST be able to ask, in a list or a detail query, what they can do to each node (update, delete, change owners) and to each field (update). The answer MUST come from the same decision as the change check. In Infrahub Community, the answer MUST be the decision for the kind, as today.
  - Check: user story 6, scenario 11. For each case, the reported value matches the result of the mutation.

#### Account group tree

- **FR-051**: With the group tree setting on, a member of a subgroup MUST count as a member of every group above it, for roles and for owners. Membership MUST count downward only. With the setting off, which is the default, Infrahub MUST follow direct membership only, as today (D-15).
  - Check: user story 7, scenarios 1 to 3. The existing permission tests pass with groups that have parents.
- **FR-052**: A report MUST list the users who would gain roles through parent groups, before an administrator turns the setting on.
  - Check: a fixture with a parent group that has a role.

### Storage constraint: option B

This section is a constraint for the plan. It comes from the request to write one spec for each storage option of the [engineering design, section 6][eng]. The names in this section are the examples of the design, not decisions.

#### How option B stores owners

- Each owner of a node is one `HAS_OWNER` edge from the node vertex to the owner. Today, only attribute vertices and relationship vertices have this edge.
- Each owner of an attribute is one `HAS_OWNER` edge from the attribute vertex. The owner edge that an attribute has today is one of them.
- Edge properties tell the other owners apart:
  - `field`: an owner of a relationship field, such as `interfaces`. The edge starts at the node vertex.
  - `given`: an owner that a profile or an object template gives to its nodes. The edge starts at the vertex of the profile or template.
- One shared marker vertex means "own state". The edges from a vertex give its state:
  - no `HAS_OWNER` edge: inherit
  - only the edge to the marker: no owner
  - the edge to the marker and edges to owners: those owners
- Infrahub already uses shared vertices, for example the two `Boolean` vertices of `IS_PROTECTED`.
- The links do not change. The owner of one link stays on its relationship vertex (D-9).
- Option B adds no vertex for each set of owners. On the data of the benchmark of 2026-11-09, it added 532,900 edges and 1 vertex.

#### What option B needs to meet the requirements

- FR-037: existing attribute owners have no edge to the marker. The upgrade must add one, or the read must treat an owner edge without a marker as the own state.
- FR-037: today a branch can write an owner on an attribute that has another owner on the default branch. A read of several owner edges returns both. The option E prototype needed an upgrade step that hides the owner that the branch replaced. Option B stores attribute owners in the same way, so it needs the same step.
- FR-008: when a branch deletes an owner group, the merge closes the owner edges to it today. The marker edge stays, so the node shows "no owner", not "deleted group". The merge must keep these owner edges, as a delete on the default branch does.
- FR-040: when a node changes kind, the migration copies only the latest edge between the node and each other vertex, and gives the new edge a fixed set of properties. It does not copy the outgoing `HAS_OWNER` edges of a node today. With option B:
  - if a node and one of its relationship fields have the same owner, two edges go from the node vertex to the same owner vertex, and the migration keeps one
  - if an account group is an owner and a source of the same node, a `HAS_OWNER` edge and a `HAS_SOURCE` edge end at the group, and the migration keeps one
  - the `field` and `given` properties are lost
  - so the kind migration must change before option B is safe
- FR-041: the `field` property must follow a field rename and a field removal. This was not checked in the code.
- FR-029 and FR-030: the diff and the merge do not read edges from the node vertex today. This is new work.
- FR-014 and FR-029: three readers take the latest `HAS_OWNER` edge of an attribute: the `owner` field of today, the diff labels and the changelog. With several edges, they return only one owner, and they can return the marker. Each one must handle several owners and skip the marker.
- FR-030: the diff query must use one pattern for each edge type and a hint for the index on the branch of `HAS_OWNER`. This index exists today (`owner_branch`), so option B needs no new index. Without the pattern and the hint, Neo4j scans all node vertices (357 ms against 14.3 ms in the benchmark of 2026-11-09).
- FR-032: two writes do not create a vertex for a set, so two branches cannot create the same set twice. Two branches can still leave two active edges between the same two vertices.

#### What the benchmarks measured for option B

- Benchmark of 2026-11-09, plain Cypher on a copy of a stack with 10,004 devices and 480,009 interfaces, 5 rounds:
  - Most reads cost the same as with option E, within 8%.
  - Stored owners of 50 devices: 4.2 ms. Owners that apply to 50 interfaces: 22.6 ms. Owners that apply to one interface: 3.3 ms.
  - Owner filter on all devices: 1.4 s. Owner filter on all interfaces: 19.6 s.
  - Find the nodes with the own owner of one group: 21.1 ms, against 15.3 ms for option E. The group vertex also receives the edges of field owners and of profile owners.
  - Diff of the owner changes on a branch, with one pattern for each edge type and an index hint: 14.3 ms, against 27.9 ms for option E.
  - Writes: 1.4 to 2.5 ms for each call.
  - Reads that do not ask for owners cost the same as before.
- Not measured: the merge, the kind migration, the cost through GraphQL and concurrent writes.
- No prototype of option B exists. The benchmark queries are the queries of the option E prototype, changed for the storage of option B.

#### Open points of option B

The engineering design lists these points for option B:

- The label of the marker vertex and the names of the edge properties.
- Where Infrahub stores the "from template" origin. The benchmark used a separate edge from the node vertex to the template.
- How to store the owners that a profile or an object template gives, so that the kind migration does not lose them. The design does not say how option B stores the owners that a profile gives to one field. The benchmark used both the `field` and the `given` property on one edge.
- Whether the merge keeps the owner edges to a deleted group.
- The form of the diff query.

The engineering design lists these points for option E only. Option B also stores several owner edges on one vertex, so this spec lists them for option B too:

- What the merge does when two branches leave two active edges between the same two vertices.
- What the `owner` field of today returns when its owner node is deleted.
- How many code paths read the latest `HAS_OWNER` edge of an attribute. Three are known.

### Key Entities *(include if feature involves data)*

- Owner: an existing account or account group. Repositories can no longer own. Today repositories can also own ([design, section 4][design]).
- Owners that apply: the owners that Infrahub resolves for a node or a field, in the order of D-6. They are own owners or inherited owners. Deleted owners do not count.
- Owner state of a node (new): inherit, own owners or no owner.
- Owner state of a field (existing for attributes, new for relationship fields): the same three states. The owners of a relationship field belong to the node, with one state per field (D-8).
- Origin: where the owners that apply come from: the item itself, a profile, an object template, a parent, or the node of the field. The origin node is the node that holds them.
- Node source (new): a list. A source can be an account, an account group, a repository, a resource pool, a profile or an object template. Field sources stay as they are.
- Profile and object template (existing): each gives owners to nodes and to the fields of nodes, and keeps its own owners.
- Link owner (existing): the owner of one relationship link. It stays unchanged, and no check reads it.
- Change check (new): the place in a mutation where Infrahub Enterprise decides if the change is allowed. In Community, it allows what is allowed today.
- "Applies to" setting (new): a setting on an object permission. In Community, only "all nodes" is valid.

## Success Criteria *(mandatory)*

### Reference data set

- 10,000 devices with 48 interfaces each
- A location hierarchy 5 levels deep
- 50 account groups that own nodes

Product confirms the reference data set and the numbers below before step 1 is merged ([eng, section 5][eng], which is empty). Until then, the plan and the spike use them.

### Measurable Outcomes

"Today" means the same operation on the same data set before this work.

- **SC-001**: A list query without owners in its fields or filters takes at most 5% longer than today.
- **SC-002**: Create, update and delete, object file loads and generator runs take at most 5% longer than today, for a customer who does not use owners.
- **SC-003**: The owner filter on interfaces returns the first page of 50, with the correct count, in under 2 seconds.
  - Not met today with either storage option: about 19 seconds for 480,000 interfaces in plain Cypher (benchmark of 2026-11-09), and about 6.7 seconds for 200,000 interfaces through GraphQL on the option E prototype. Most of the cost is the walk up to the parents and to the profiles, not the owner storage. See "Open questions".
- **SC-004**: The "no owner" filter on devices returns the first page, with the correct count, in under 2 seconds.
- **SC-005**: After a change of owners on a device or a profile, the next read of every node that inherits from it shows the new owners.
- **SC-006**: A page of 50 nodes with their owners takes at most 100 ms longer than the same page without owners.
  - This limit is a proposal of this spec. No source sets it. The option E prototype measured 35 to 50 ms through GraphQL.
- **SC-007**: After the upgrade, 100% of the existing permission tests pass without changes, and every existing role gives the same results.
- **SC-008**: On Infrahub Community, a mutation takes at most 5% longer than today because of the change check. Source: the limit that the session of 2026-10-27 set for users whose permissions apply to all nodes.

The spike measures two limits for Infrahub Enterprise on this storage:

- **SC-009**: The owner check adds at most 10% to a mutation on one interface at depth 6.
- **SC-010**: A generator run over 10,000 owned nodes takes at most 10% longer than today.

## Assumptions

- Account groups exist in Infrahub before files refer to them by name.
- Hierarchies are at most 6 levels deep. The spike checks this on real schemas.
- Most nodes use 0 to 2 profiles.
- New nodes get no default owner. Templates and profiles give owners.
- A branch-agnostic node keeps its owners on all branches, like its other data.
- No node has owners or sources before the upgrade.
- The owner and source filters are part of Infrahub Community, until product decides Q-23.
- Infrahub does not limit the number of owners of one item. A reviewer asked about a limit and pagination ([eng, comment of 2026-11-09][eng]).
- Generators and repository imports run with the account of the task worker, as today.

## Out of scope

- The checks of Infrahub Enterprise: which permissions count for an owned node, their ranking, who can change owners, the check of a cascading delete, the role preset, and the queries that explain a decision.
- Any restriction of view by owner or by field (D-12).
- All frontend changes (decision of 2026-11-10). It is not decided where they are specified. The earlier sources name these changes:
  - the owners of a node and of each field on the detail view, with the origin of each owner
  - owners and sources columns in list views, and the owner and source filters in list views
  - the owner state of a node and of single fields in the create and edit forms
  - bulk actions on the owners of selected nodes in list views, with a warning before a node stops inheriting (session of 2026-10-27)
  - the display of owner and source changes in the proposed change diff and in the activity log
  - disabled items for what the user cannot change, with the reason on hover, in place of `is_protected` in the edit form
- Several sources per field, source states, inherited sources, and sources from profiles and object templates.
- Filters on the owners of single fields, apart from the existing `<attribute>__owner__id`. Sorts by owner or by source.
- A group tree built from the identity provider. Sign-in creates groups with no parent.
- Removal of group memberships at sign-in when a user leaves a group in the directory.
- Approvers derived from owners, data constraints, and profiles attached automatically ([INFP-342][INFP-342]).
- Two gaps in the view checks of today, found during the sessions. They do not depend on owners and need separate issues: some REST endpoints check authentication only, and a query on a generic checks view on the generic only.

## Open questions

### Decisions that product owes

- Which edition gets the owner and source filters (FR-018, FR-019, FR-034), and the refusals that name the field, the missing permission and the owners ([design, Q-23][design]). If the filters go to Enterprise, they need an extension point, and user story 1 changes for Community.
- Whether one change in the history of the profile is enough for audits (D-6). The recommendation of 2026-10-27: keep D-6, and link the origin "profile" to the activity log of the profile.
- The reference data set and the numbers of the success criteria.
- Whether the `ownership` block must give the profile as origin node for a field whose node takes its owners from a profile (E-15).

### Questions for engineering

- Which storage option the team builds: B or E. See "Storage constraint" in both specs.
- How the owner filter meets SC-003 on the largest kinds. The session of 2026-10-22 named a fallback: an internal index of the owners that apply, which is not branch data.
- Which pairs of owner changes on the default branch and on another branch conflict (FR-030). Two rules exist. They give different results when two branches change different owners of the same node:
  - The engineering design expects no conflict, because each owner is a separate edge. This was not tested.
  - The option E prototype compares the whole list of owners of an item, so it reports a conflict.
- The result of two writes of owners on the same item at the same time (FR-032). This spec proposes that the state of the last write stays.
- The depth limit of the walk to the parents, and the result for a node beyond the limit (E-16).
- Whether a change of owners or sources updates the "updated at" and "updated by" metadata of the node (FR-053).
- The names of the fields, filters and object file keys. Open points of the GraphQL shape ([eng, section 2][eng]): the field name in the error messages is not the same for all errors, and the mutation output has no `node_metadata`.
- A reviewer proposed generated fields on profiles and templates for the owners that they give, like the fields for resource pools ([eng, comment of 2026-11-03][eng]).
- A reviewer noted that a profile replaces the source of a template on an attribute today, so the read of both origins can need several sources ([eng, comment of 2026-11-09][eng]).

## Earlier work on the dev VM

Nothing below is committed or pushed. The paths are on the dev VM.

- The first spec, with the design copy of 2026-10-21: `/home/ubuntu/specs-handoff/infp-489-ownership-phase-1/`.
- The spec sets of phases 1 to 3, with plans, tasks, research and measurements, and a draft implementation with storage option A (ruled out): `dev/specs/infp-489-ownership-phase-{1,2,3}/` in the worktree `/home/ubuntu/emdash/worktrees/infrahub-9a2bed99/rbac-ownership-draft-sa8iy`. `grilling-handoff.md` in phase 1 lists what the draft found.
- The prototype of storage option E, with the GraphQL shape of 2026-11-09 and tests for diff, merge, templates and the upgrade: the worktree `/home/ubuntu/emdash/worktrees/infrahub-9a2bed99/cozy-hotels-rule-9wekc`.
- The benchmark of options B and E: `be-bench/results.md` in the scratchpad of the grilling session, under `/tmp/claude-1000/-home-ubuntu-emdash-worktrees-infrahub-9a2bed99-grill-rbac-feature-5f4ex/`. This folder is temporary.
- The briefs of phases 2 and 3 (decisions H-1 to H-22 and I-1 to I-15) were temporary files and are gone. Their text is in the transcript of the grilling session: `/home/ubuntu/.claude/projects/-home-ubuntu-emdash-worktrees-infrahub-9a2bed99-grill-rbac-feature-5f4ex/20c9e721-6094-4523-9f33-271dab7da8f6.jsonl`.

## Notes for planning

These points are constraints for `/speckit-plan`, not requirements for users.

### Constitution alignment

- I. Schema-driven: the owner states, node sources, the "applies to" setting and the new permission values are defined in the schema layer.
- II. Branch-safe: all owner data is stored separately on each branch. The upgrade closes edges and deletes nothing. The merge, rebase and conflict behaviour of the new data must be specified and tested (FR-030).
- III. Contracts: the GraphQL fields, filters and deprecations are defined before implementation. The change check is an interface with two implementations: the Community one that allows everything, and the Enterprise one.
- IV. Tests: resolution, filters, the upgrade and each case of FR-030 need tests. E2E tests in `tests/e2e/` run the user stories through the API on the full stack. This spec adds no E2E test of a page, because it holds no frontend change. The kind change and the field rename need an integration Docker test, because they are schema migrations.
- V. Query performance: the walk up to the parents is the main read cost. Each new query needs `EXPLAIN` and `PROFILE` checks on a large data set, with SC-001 to SC-006 as the limits.
- VII. Simplicity: sources stay on nodes only. An index of the owners that apply is built only if the spike shows that SC-003 needs it.

### Governance gates that this work crosses

- Database structure change and graph migration.
- Core schema change: the "applies to" setting, the action for changing owners and the global permission to manage ownership.
- GraphQL schema change, with no new mutation.
- Authentication and authorization change: the change check, and the group tree setting.
- A new configuration setting: the group tree.
- Python SDK submodule change. The change on the SDK repository comes first.

[design]: https://app.notion.com/p/3f2228b8302581699421d37be2c6f094
[eng]: https://app.notion.com/p/401228b830258034af14d485d00b0314
[INFP-753]: https://opsmill.atlassian.net/browse/INFP-753
[INFP-489]: https://opsmill.atlassian.net/browse/INFP-489
[INFP-477]: https://opsmill.atlassian.net/browse/INFP-477
[INFP-478]: https://opsmill.atlassian.net/browse/INFP-478
[INFP-342]: https://opsmill.atlassian.net/browse/INFP-342
