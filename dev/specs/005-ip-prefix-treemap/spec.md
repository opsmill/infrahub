# Feature Specification: IP Prefix Tree Map

**Feature Branch**: `pmc/ip-prefix-treemap-viz-5dfe40f9`

**Created**: 2026-10-03

**Status**: Draft

**Input**: User description: "IP Prefix Tree Map: add a "Tree Map" tab to the IP prefix detail page that renders a one-level treemap of the prefix's direct children and free blocks, tiles sized by address space, allocated tiles filled by utilisation, click a child to drill down, click a free block to create a prefix."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See where a prefix's space has gone (Priority: P1)

A network engineer planning address space in a large supernet (a /8, a /16, or an IPv6 /32 to /48) opens the prefix in the IP Address Manager and selects a new "Tree Map" tab. The tab shows the prefix as a rectangle fully tiled by its direct children and its free blocks. Each tile's area is proportional to the share of the parent's address space it covers, so a /16 inside a /8 is 1/256 of the area. Allocated children are drawn in an accent style with an inner fill proportional to that child's own utilisation; children flagged as pools use a second colour so they stand out from static allocations. Free blocks are drawn in a visibly empty style so the eye reads holes first. Hovering a tile reveals its details.

**Why this priority**: This is the whole point of the feature. Today the Children table shows consumption row by row and the header utilisation percentage hides fragmentation. The engineer cannot see at a glance which children consume the block or where the largest contiguous free space is. Rendering one level with free space visible answers both questions without scrolling and without any other change.

**Independent Test**: Open the Tree Map tab on a prefix that has a mix of child prefixes and free space. Verify the tiles present, their relative areas, their fills and the hover details against the Children tab for the same prefix. Delivers value on its own as a read-only view.

**Acceptance Scenarios**:

1. **Given** prefix 10.0.0.0/8 has direct children 10.0.0.0/16, 10.1.0.0/16 and 10.2.0.0/16 and nothing else, **When** the user opens its Tree Map tab, **Then** three allocated tiles each cover 1/256 of the map area, and the remaining area is covered by free-block tiles whose CIDRs equal the available prefixes the Children tab lists for the same parent.
2. **Given** a child prefix that is 80% utilised and a sibling that is 2% utilised, **When** the map renders, **Then** the first tile's inner fill covers 80% of the tile and the second's covers 2%, and the difference is visible without a legend.
3. **Given** the map is rendered, **When** the user hovers an allocated tile, **Then** the CIDR, description, member type, utilisation and member count of that child are shown, **and When** the user hovers a free tile, **Then** its CIDR is shown.
4. **Given** a prefix whose children fully cover its space, **When** the map renders, **Then** no free tiles appear.
5. **Given** a prefix with no children, **When** the map renders, **Then** the whole area is covered by free tiles.
6. **Given** the user is working on a non-default branch where a child prefix exists only on that branch, **When** the user opens the Tree Map tab on that branch, **Then** the branch-only child appears as an allocated tile, and it does not appear when the same tab is opened on the default branch.

---

### User Story 2 - Drill down into a child (Priority: P2)

From the Tree Map, the engineer clicks an allocated child tile and lands on that child's own Tree Map tab, with the current branch and IP namespace preserved. The breadcrumb and the IP Address Manager tree sidebar update as they would for any navigation to that child. The engineer can keep descending one level at a time or use the breadcrumb to go back up.

**Why this priority**: One level at a time keeps rendering cheap and predictable, but without drill-down the engineer would have to leave the map to go deeper. Drill-down turns a single picture into a navigable hierarchy at no extra data cost.

**Independent Test**: Click a child tile and verify the route, the page header and the sidebar selection now refer to the child, with branch and namespace unchanged.

**Acceptance Scenarios**:

1. **Given** the Tree Map for 10.0.0.0/8 is rendered, **When** the user clicks the 10.1.0.0/16 tile, **Then** the page shows 10.1.0.0/16 with its Tree Map tab selected, and the branch and IP namespace in the address bar are unchanged.
2. **Given** the user drilled into a child whose members are addresses rather than prefixes, **When** the child's Tree Map tab opens, **Then** the empty state described in User Story 4 is shown rather than a silent switch to another tab.

---

### User Story 3 - Allocate into a hole from the map (Priority: P2)

The engineer spots a free block on the map, clicks it, and the existing Create IP Prefix form opens with the free block's CIDR already filled in. On submit, the form closes and the map refreshes, showing the new prefix as an allocated tile in place of the free block.

**Why this priority**: This closes the capacity-planning loop in one screen. The Children table already offers the same action on its available rows, so reusing it here costs almost nothing and turns the map from a picture into a place where work gets done.

**Independent Test**: Click a free tile, confirm the form is prefilled, submit, and confirm the new tile appears without a page reload. Repeat as a read-only user and confirm the action is disabled with an explanation.

**Acceptance Scenarios**:

1. **Given** the Tree Map for 10.0.0.0/8 shows a free tile 10.3.0.0/16 and the user may create prefixes, **When** the user clicks that tile, **Then** the Create IP Prefix form opens with the prefix field set to 10.3.0.0/16.
2. **Given** that form is open, **When** the user submits it successfully, **Then** the form closes and the map shows 10.3.0.0/16 as an allocated tile without a page reload.
3. **Given** the user lacks permission to create prefixes, **When** the user hovers or clicks a free tile, **Then** the create action is disabled and the same permission explanation used elsewhere in the IP Address Manager is shown.

---

### User Story 4 - Open the tab on an address-member prefix (Priority: P3)

The engineer opens the Tree Map tab on a prefix whose members are IP addresses rather than child prefixes (for example a /16 holding 30 hosts). Instead of a map of sub-pixel address tiles, the tab shows the prefix's utilisation meter, a one-line explanation that the map shows child prefixes, and a link to the IP Addresses tab. A prefix marked as holding addresses but which still has child prefixes (a common modelling choice for supernets) gets the map, since the decision is taken from the children the query returns, not from the member type alone.

**Why this priority**: Address-level prefixes are not the design target, but the tab must behave predictably on every prefix so drill-down never surprises the user. A clear empty state is cheap and avoids a misleading picture.

**Independent Test**: Open the Tree Map tab on an address-member prefix and verify the empty state content and the link target.

**Acceptance Scenarios**:

1. **Given** 10.0.0.0/16 has member type "address", 30 IP addresses and no child prefixes, **When** the user opens its Tree Map tab, **Then** no tiles are drawn, the utilisation meter is shown, the explanation is shown, and a link leads to the IP Addresses tab of the same prefix.
2. **Given** a /8 has member type "address" but holds five child prefixes, **When** the user opens its Tree Map tab, **Then** the map renders with one tile per child and the free blocks, not the empty state.

---

### User Story 5 - Read a very large or very fragmented prefix (Priority: P3)

The engineer opens the Tree Map tab on a prefix with hundreds or thousands of direct children, or on a prefix where some children are far too small to see (a single /32 inside a /8, or a /64 inside an IPv6 /32). The map stays legible: it renders at most a fixed number of children in address order and says so, shows the rest of the space as one tile, and it collapses tiles that would be too small to see into one "N smaller prefixes" tile and one "N smaller free blocks" tile; the smaller-prefixes tile leads the user to the Children tab and the free one lists its blocks on hover.

**Why this priority**: Real supernets are messy. Without a cap and an aggregation rule, the map either becomes unreadable or becomes slow, and tiny allocations become unclickable slivers that someone still needs to find.

**Independent Test**: Render the map for a synthetic prefix with more children than the cap, and for a prefix containing one tiny child, and verify the notice, the aggregated tiles and their link target.

**Acceptance Scenarios**:

1. **Given** a prefix with 1,200 direct children, **When** the user opens its Tree Map tab, **Then** the map shows the first 1,000 children in address order, a notice reading "showing the first 1,000 of 1,200 children", and one tile covering the address space not shown that leads to the Children tab, and the page stays responsive.
2. **Given** 10.0.0.0/8 contains three /16 children and one /32 child, **When** the map renders, **Then** the /32 does not appear as its own tile, a tile labelled "1 smaller prefix" appears instead, hovering it lists 10.x.y.z/32, and clicking it opens the Children tab for 10.0.0.0/8.
3. **Given** a prefix whose free space includes blocks below the legible minimum, **When** the map renders, **Then** those blocks are collapsed into one "N smaller free blocks" tile with a hover list.
4. **Given** an IPv6 prefix 2001:db8::/32 containing a /48 and a /64, **When** the map renders, **Then** the /48 tile covers 1/65,536 of the area or is aggregated per the legibility rule, the /64 is aggregated, and the free-block areas are exact.

---

### Edge Cases

- A child tile whose label does not fit is drawn without a label; the CIDR is still available on hover.
- A prefix with no children renders as all free space; create-from-tile works on any of those free tiles.
- A prefix that is 100% allocated renders with no free tiles and therefore no create affordance.
- The utilisation of one or more children cannot be determined (slow or failed lookup): the tile still renders with its size and CIDR, and its fill is shown as unknown rather than as 0%.
- IPv6 prefixes with extreme size ratios (a /128 inside a /32) must not break the area computation; the aggregation rule absorbs them.
- The user switches branch or IP namespace while on the tab: the map re-renders for the new context.
- The parent prefix is deleted or moved while the tab is open: the page behaves as the other tabs do for a missing object.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to open a "Tree Map" tab from the detail page of any IP prefix, alongside the existing Details, IP Addresses, Resource Pool and Children tabs.
- **FR-002**: System MUST render each direct child prefix and each free block of the current prefix as a tile whose area is proportional to the share of the parent's address space it covers, computed from prefix lengths so that the result is exact for IPv4 and for IPv6 across prefix lengths 0 to 128.
- **FR-003**: System MUST ensure the areas of all allocated and free tiles, including aggregated tiles, sum to the parent's full address space.
- **FR-004**: System MUST draw allocated tiles in an accent style with an inner fill proportional to that child's own utilisation, draw prefixes flagged as pools in a second, distinct colour family with their own legend entry, and draw free tiles in a visibly empty style (hatched) distinct from both.
- **FR-004a**: System MUST show an allocated tile's description on the tile when there is room, and otherwise mark that a description exists so the user knows to hover for it.
- **FR-005**: System MUST show CIDR, description, member type, utilisation and member count when the user hovers an allocated tile, and CIDR when the user hovers a free tile.
- **FR-006**: System MUST label each tile with its CIDR when the label fits, and omit the label otherwise.
- **FR-007**: Users MUST be able to click an allocated tile to navigate to that child's Tree Map tab, with the current branch and IP namespace preserved.
- **FR-008**: Users MUST be able to click a free tile to open the existing Create IP Prefix form prefilled with the free block's CIDR, subject to the same create permission and disabled-state explanation used by the Children tab's available rows.
- **FR-009**: System MUST refresh the map after a successful create from a free tile so the new child appears as an allocated tile without a page reload.
- **FR-010**: System MUST render an empty state for prefixes whose member type is "address" and that have no child prefixes, showing the prefix's utilisation meter, a one-line explanation that the map shows child prefixes, and a link to the IP Addresses tab of the same prefix. An address-type prefix that does hold child prefixes gets the map.
- **FR-011**: System MUST load at most 1,000 direct children per map in address order, render them, and whenever more exist display a notice of the form "showing the first 1,000 of N children" together with one aggregated tile covering the address space not shown that leads to the Children tab.
- **FR-012**: System MUST collapse allocated tiles below a legible minimum area into one "N smaller prefixes" tile and free tiles below the same minimum into one "N smaller free blocks" tile, each listing its members on hover; clicking the smaller-prefixes tile MUST open the Children tab of the current prefix.
- **FR-013**: System MUST render the map for the branch and IP namespace currently selected in the page, and re-render when either changes.
- **FR-014**: System MUST keep an allocated tile visible, sized and labelled when that child's utilisation cannot be determined, showing the fill as unknown rather than as zero.

### Key Entities *(include if feature involves data)*

- **IP Prefix**: An existing object representing a CIDR block within an IP namespace. The map uses its prefix, member type (prefix or address), pool flag, utilisation, description, direct child prefixes and member count. No new attributes are added.
- **Free block**: An existing, computed notion representing a CIDR within a parent prefix that no child prefix covers. It has no stored identity; it is derived from the parent and its children on read and is already listed as "available" rows on the Children tab.
- **IP Namespace**: An existing scope for the prefix hierarchy. The map always operates within the namespace selected on the page.

No new entities are introduced.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the demo dataset, the Tree Map for a prefix with up to 256 direct children is fully rendered within 3 seconds of opening the tab in a warm session.
- **SC-002**: In a usability check with three network engineers, each identifies the largest contiguous free block in a /8 with mixed allocations in under 10 seconds, with no scrolling.
- **SC-003**: For every prefix in the demo dataset, the set of free-block CIDRs shown on the map equals the set of available rows on the Children tab for the same prefix, and allocated plus free tile areas sum to the parent's address space.
- **SC-004**: A child prefix created from a free tile appears as an allocated tile without a page reload in 100% of end-to-end test runs.
- **SC-005**: A prefix with 1,000 or more direct children renders the capped view and its notice within 5 seconds, and the page remains responsive to hover and click throughout.

## Assumptions

- The primary user is a network engineer planning space in a large supernet. Address-level pools and demonstration audiences are not the design target and do not drive scope.
- The existing per-prefix availability computation defines what a free block is; the map displays those blocks and does not recompute availability on its own.
- The utilisation shown on a child tile is that child's own utilisation as the platform already defines it, which depends on the child's member type and pool flag.
- The 1,000-child cap is an order-of-magnitude guess, not a measured threshold, and is expected to be a single adjustable constant.
- The cap keeps children in address order rather than by size, because free space can only be computed correctly within a contiguous address window. The space not covered by the loaded children and free blocks is shown as one aggregated tile so that tile areas still sum to the parent.
- The legible minimum tile area is a presentation threshold chosen during implementation; the requirement is that tiles below it are aggregated, not the exact pixel value.
- SC-001 is the criterion most at risk, because per-child utilisation is computed on read today. The feature ships with no backend change; if SC-001 is missed on the demo stack, a batched utilisation lookup is raised as a separate, explicitly gated change rather than built pre-emptively.
- The "N smaller prefixes" tile links to the unfiltered Children tab of the current prefix; a filtered link is a possible later refinement.
- The tab label is "Tree Map".
- IPv4 and IPv6 are both supported in the first release.
- Existing create permissions, branch selection and namespace selection are reused unchanged; the feature adds no authorisation rules.

## Out of Scope

- Nested rendering beyond one level (grandchildren inside child tiles); deferred until a batched subtree lookup justifies it.
- Colouring tiles by role, status, resource pool membership, or a utilisation heat scale.
- Rendering individual IP addresses as tiles.
- Zoom, pan, a size-metric toggle or image export.
- Any backend change, including a batched or subtree utilisation lookup.
- Changes to the Children tab. (The IP Address Manager tree sidebar did change on this branch: it now follows in-app navigation, a pre-existing gap that drill-down made constant.)
