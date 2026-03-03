# Feature Specification: IPAM Parent Prefix Lookup

**Feature Branch**: `001-ipam-prefix-lookup`
**Created**: 2026-02-17
**Status**: Draft
**Input**: User description: "IP address/prefix lookup with parent prefix fallback for IPAM search"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Find Parent Prefix for a New IP Address (Priority: P1)

A network engineer needs to create a new IP address (e.g., 10.1.2.45) in Infrahub. They don't know which prefix it belongs to. They open the search anywhere dialog (Cmd+K), type the full IP address, and the system returns the containing parent prefix(es) (e.g., 10.1.2.0/24) with namespace context. The engineer clicks on the result to navigate directly to that prefix, where they can create the new IP address.

**Why this priority**: This is the core use case driving the feature. Without it, customers must manually calculate prefix containment or navigate hierarchies, which they describe as making "the IPAM feature useless to them." This directly addresses customer retention and competitive parity.

**Independent Test**: Can be fully tested by searching for any valid IP address in the search dialog and verifying that containing prefixes are returned. Delivers immediate value by eliminating manual prefix calculation.

**Acceptance Scenarios**:

1. **Given** prefixes 10.0.0.0/8, 10.1.0.0/16, and 10.1.2.0/24 exist in the system, **When** the user searches for "10.1.2.45" in search anywhere, **Then** all three containing prefixes are returned in a dedicated "Parent Prefixes" section, ordered from most specific (10.1.2.0/24) to least specific (10.0.0.0/8), each showing its namespace.
2. **Given** an IP address object 10.1.2.45 already exists in the system within prefix 10.1.2.0/24, **When** the user searches for "10.1.2.45" in search anywhere, **Then** the existing IP address object is returned as an exact match in the search results AND the containing parent prefixes are returned in the dedicated "Parent Prefixes" section.
3. **Given** no prefix contains the searched IP address, **When** the user searches for "192.168.1.1" and no matching prefix exists, **Then** the "Parent Prefixes" section shows no results (empty state) with an appropriate message. Regular search results may still appear if there are text matches.
4. **Given** the same IP address exists within prefixes in multiple namespaces, **When** the user searches for that IP address, **Then** results from all namespaces are returned, each clearly labeled with its namespace.

---

### User Story 2 - Find Parent Prefix for a Known Prefix (Priority: P2)

A network engineer searches for a prefix (e.g., 10.1.2.0/24) in the search anywhere dialog. The system returns both exact matches (the prefix itself if it exists) and any containing parent prefixes (e.g., 10.1.0.0/16, 10.0.0.0/8). This helps the engineer understand the prefix hierarchy and navigate to the correct location.

**Why this priority**: Extends the core lookup to prefix inputs, supporting engineers who work with CIDR notation directly. Important for hierarchy navigation but secondary to the primary IP address use case.

**Independent Test**: Can be tested by searching for a prefix in CIDR notation and verifying that both exact matches and parent prefixes are returned.

**Acceptance Scenarios**:

1. **Given** prefixes 10.0.0.0/8, 10.1.0.0/16, and 10.1.2.0/24 exist, **When** the user searches for "10.1.2.0/24", **Then** the exact match (10.1.2.0/24) is returned as a regular search result (per FR-013) and the "Parent Prefixes" section shows only the true containing parents (10.1.0.0/16, 10.0.0.0/8). The exact match does not appear in the "Parent Prefixes" section.
2. **Given** a prefix does not exist but parent prefixes do, **When** the user searches for "10.1.3.0/24" (not created yet), **Then** the containing parent prefixes (10.1.0.0/16, 10.0.0.0/8) are returned.

---

### User Story 3 - Partial IP Falls Back to Text Search (Priority: P2)

A user types a partial IP string (e.g., "10.1.2") or a hostname into the search anywhere dialog. Since this is not a valid complete IP address or CIDR prefix, the system treats it as a regular text search query, preserving existing behavior with no changes.

**Why this priority**: Ensures backward compatibility. Existing text search behavior must not be altered or degraded by the new IP lookup feature.

**Independent Test**: Can be tested by entering partial IP strings and non-IP text and verifying that existing text search results are returned unchanged.

**Acceptance Scenarios**:

1. **Given** existing search behavior for partial strings, **When** the user types "10.1.2" (no complete IP or CIDR notation), **Then** the system performs a regular text search and returns results matching that string (existing behavior, unchanged).
2. **Given** a non-IP search query, **When** the user types "router-core-01", **Then** the system performs a regular text search (existing behavior, unchanged).

---

### User Story 4 - Navigate from Search Result to Create IP Address (Priority: P3)

After finding the parent prefix via search, the user clicks on the prefix result and navigates to the prefix detail page. From there, they can create a new IP address within that prefix using existing workflows.

**Why this priority**: Completes the end-to-end workflow but relies on existing navigation and IP creation functionality. The search result linking is the new piece.

**Independent Test**: Can be tested by clicking a prefix search result and verifying navigation to the prefix detail page.

**Acceptance Scenarios**:

1. **Given** a parent prefix result is displayed in search results, **When** the user clicks on the prefix, **Then** they are navigated to the prefix detail page where they can create new IP addresses.

---

### Edge Cases

- What happens when the user searches for an IPv6 address with non-canonical formatting (e.g., "2001:0db8::1" vs "2001:db8::1")? The system should normalize IPv6 addresses before lookup and return consistent results regardless of input formatting.
- What happens when the user searches for a /31 point-to-point prefix? The system should return results normally; /31 prefixes are valid and have two usable addresses.
- What happens when the user searches for a /32 (IPv4) or /128 (IPv6) host prefix? The system should return the exact match if it exists and any containing parent prefixes.
- What happens when the user searches for an IP address that falls within overlapping prefixes across different namespaces? All matching prefixes from all namespaces should be returned, each labeled with its namespace.
- What happens when the search input is ambiguous (e.g., "10.1.2.3" could be an IP or part of a longer string)? If the input parses as a valid IP address or CIDR prefix, it should be treated as an IP lookup. Otherwise, fall back to text search.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST detect when a search query is a valid IP address (IPv4 or IPv6) or CIDR prefix notation and trigger the parent prefix lookup in addition to the existing text search. Both the regular search results and the parent prefix results are displayed.
- **FR-002**: System MUST return all prefixes that strictly contain the searched IP address or prefix, across all IP namespaces, with no cap on result count. When searching for a prefix, the exact-match prefix itself MUST NOT appear in the "Parent Prefixes" section (it appears as a regular search result per FR-013 instead).
- **FR-003**: System MUST order results by prefix specificity, with the most specific (longest) prefix first.
- **FR-004**: System MUST display the namespace for each returned prefix result so users can distinguish between overlapping IP spaces.
- **FR-005**: System MUST fall back to existing text search behavior when the query is not a valid complete IP address or CIDR prefix (e.g., partial IPs, hostnames, or general text).
- **FR-006**: System MUST normalize IPv6 input before performing the lookup to ensure consistent matching regardless of input formatting variations.
- **FR-007**: System MUST support both IPv4 and IPv6 addresses and prefixes.
- **FR-008**: System MUST display parent prefix lookup results in a dedicated "Parent Prefixes" section within the search anywhere UI, visually separated from regular text search results, so users can clearly identify containment-based results. Each parent prefix result MUST use the same result format and detail level as regular search results for IP address/prefix objects (same fields, same layout, same click behavior).
- **FR-009**: System MUST allow users to click on a prefix result to navigate to the prefix detail page.
- **FR-010**: The parent prefix lookup MUST NOT degrade the performance of existing text search queries. Non-IP search queries must follow the same execution path as before.
- **FR-011**: The parent prefix lookup MUST respect the user's currently active branch context, returning only prefixes visible on that branch (consistent with existing search behavior).
- **FR-012**: All existing search anywhere behavior MUST remain unchanged. The parent prefix lookup is purely additive — it adds a new results section when an IP/prefix is detected but MUST NOT alter, remove, or interfere with any other search results, result ordering, or UI behavior.
- **FR-013**: When the search query is a valid IP address or CIDR prefix, the system MUST return exact-match IP address or prefix objects (if they exist in the system) in the search results, in addition to the parent prefix lookup results. This ensures that searching for an existing IP address or prefix always surfaces that object.

### Key Entities

- **IP Prefix**: A network prefix in CIDR notation (e.g., 10.1.2.0/24) that represents a range of IP addresses. Has attributes including a binary address representation used for containment lookups.
- **IP Address**: A single host address (e.g., 10.1.2.45) that falls within one or more prefixes.
- **IP Namespace**: A logical grouping that allows overlapping IP spaces to coexist. Prefixes and addresses belong to a namespace.
- **Search Query**: The user-entered string in the search anywhere dialog. Can be either an IP/prefix (triggering the new lookup) or general text (triggering existing search).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can find the correct parent prefix for any valid IP address in under 3 seconds from typing the address to seeing results in the search dialog.
- **SC-002**: 100% of valid IP address and CIDR prefix searches return all containing parent prefixes across all namespaces.
- **SC-003**: Existing text search queries (non-IP) experience zero performance regression; response times remain unchanged.
- **SC-004**: Users can complete the full workflow (search for IP, find parent prefix, navigate to prefix page) in under 5 clicks.
- **SC-005**: IPv6 address searches produce correct results regardless of input formatting (compressed, expanded, mixed notation).
- **SC-006**: Search results clearly indicate the namespace for each returned prefix, enabling users to distinguish overlapping IP spaces without additional navigation.

## Clarifications

### Session 2026-02-17

- Q: Should the parent prefix lookup respect the user's current branch context? → A: Yes, lookup searches prefixes on the active branch only (same as existing search behavior).
- Q: Should there be a maximum number of parent prefixes returned? → A: No cap; return all containing prefixes, ordered most specific first.
- Q: When an IP is detected, should text search results also be shown alongside prefix lookup results? → A: Yes; regular text search results (including existing IP address object matches) remain unchanged. The parent prefix lookup adds a dedicated section alongside the existing results.
- Q: What happens when a user searches for a valid IP address that already exists as an IP address object in the system? → A: The existing IP address object appears as an exact match in the search results (new behavior per FR-013), and the containing parent prefixes appear in the new dedicated "Parent Prefixes" section.
- Q: Should any other existing search anywhere behavior be altered by this feature? → A: No. This feature is purely additive. All existing search behavior, result types, ordering, and UI must remain unchanged.

### Session 2026-03-03

- Q: Does the current search reliably return exact IP address/prefix objects when searching by their address value? → A: No, it does not. The spec must add an explicit requirement (FR-013) to ensure exact-match IP address and prefix objects are returned in search results when the query matches their address value. This is new behavior this feature must deliver, not existing behavior.
- Q: What metadata should each prefix result display in the "Parent Prefixes" section? → A: Parent prefix results must use the exact same result format as regular search results for IP address/prefix objects (same fields, layout, and click behavior). This supersedes the earlier "prefix notation, namespace, and description" answer — the results should match the full detail level of regular search results.
- Q: When searching for an existing prefix, should it appear in both regular results and the "Parent Prefixes" section? → A: No. The exact-match prefix appears only as a regular search result (per FR-013). The "Parent Prefixes" section shows only true containing (strictly larger) parent prefixes, avoiding duplication.
- Q: Should parent prefix results use the same visual format as regular search results for IP objects? → A: Yes. Parent prefix results must use the exact same result format/component as regular search results (same fields, layout, click behavior), just displayed within the "Parent Prefixes" section.

## Assumptions

- The system already stores IP prefixes with binary address representations that can be used for containment queries.
- IP namespaces are an existing concept in the system and prefixes are already associated with namespaces.
- The search anywhere dialog (Cmd+K) is an existing UI component that can be extended to handle a new result type.
- The existing prefix hierarchy and reconciliation logic provides a foundation for containment lookups.
- Standard IP address parsing (handling IPv4, IPv6, CIDR notation) is sufficient for detecting IP-type search queries.
- /31 and /32 prefixes (IPv4) and /127 and /128 prefixes (IPv6) are treated as valid prefixes with no special-case behavior needed beyond standard containment logic.

