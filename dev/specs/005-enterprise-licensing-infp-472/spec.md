# Feature Specification: Enterprise Licensing, Community Contract

**Feature Branch**: `enterprise-licensing-infp-472`

**Created**: 2026-10-04

**Status**: Draft

**Input**: User description: "INFP-472 — Licensing in Infrahub Enterprise. Source of truth: the design doc (Notion, 'Licensing in Infrahub Enterprise'); its Behaviour table, decisions D1–D12 and open questions are approved input. Scope for this repo (opsmill/infrahub, community): the first delivery part, which merges with no visible effect — license content and states, banner rules, the response header, the license object on /api/info, the telemetry license block, the upgrade command license section, the replaceable license service with a community default, the frontend banner and About dialog rows, and pyjwt -> pyjwt[crypto]. The Enterprise checker and accepted issuers live in opsmill/infrahub-private and are out of this repo's scope; the SDK and MCP warnings are follow-ups in their own repos."

**Source of truth**: [Licensing in Infrahub Enterprise](https://app.notion.com/p/3ef228b830258130b788d4e2d9c2d357) (design doc), [INFP-472](https://opsmill.atlassian.net/browse/INFP-472) (product card), [Licensing System Discovery Brief](https://app.notion.com/p/02a228b8302582e496d001c15b151225).

## Context

Infrahub Enterprise is getting a license that is checked offline and only ever produces banners, never a cutoff. The design splits the work in three deliveries:

1. **This feature**: everything that lives in this repository. It merges with no visible effect, because the community edition has no license and the Enterprise checker is not active until a production issuer exists.
2. The first licensing release: the Enterprise checker with a production issuer, banners for super-admins only.
3. The second licensing release: banners for every user and the response header.

This specification covers delivery 1 only. It defines the license data, the license states, who sees which banner in which release, and every surface that shows the state: the info endpoint, the About dialog, the banner, the response header, the telemetry snapshot and the upgrade command. The Enterprise package later supplies a license service that reads and verifies the license; this repository provides the contract it plugs into, and a community default that always reports that no license is required.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Existing deployments see no change when this ships (Priority: P1)

An operator upgrades a Community or Enterprise deployment to the release that contains this feature. Nothing changes in behaviour: no banner, no new response header, no license section in the upgrade output, and the About dialog shows the same rows as before. The only additions are a license object on the info endpoint that reports "not required", and the license key setting in the configuration reference.

**Why this priority**: The design requires this part to merge before the issuing tool is chosen and before any customer has a license. If it shows anything, paying customers would see "running without a license" before receiving one.

**Independent Test**: Run Community and Enterprise (with no license service registered by the Enterprise package) and check every surface: the UI, the info endpoint, response headers on REST and GraphQL, the telemetry snapshot and the upgrade command output.

**Acceptance Scenarios**:

1. **Given** a Community deployment, **When** a signed-in user opens any page, **Then** no license banner is shown and the About dialog shows the same rows as today.
2. **Given** a Community deployment, **When** any REST or GraphQL request is made, **Then** the response carries no license status header.
3. **Given** a Community deployment, **When** a signed-in user reads the info endpoint, **Then** the license object reports that no license is required and carries no license details.
4. **Given** a Community deployment, **When** the operator runs the upgrade command with or without its check option, **Then** the output has no license section and the exit code is unchanged.
5. **Given** a Community deployment, or an Enterprise deployment with no license service registered, with the license key environment variable set, **When** Infrahub starts, **Then** it ignores the value, logs that once at INFO level without the value, and starts normally.

---

### User Story 2 - Signed-in users can see the license state and details (Priority: P1)

When the Enterprise package supplies a license service, every signed-in user can see whether the deployment is licensed and, if so, to whom, which type, which tiers and until when. Super-admins additionally see why a license could not be verified.

**Why this priority**: The state and details are the base that every other surface reads. Without them, the banner, header, telemetry and upgrade output have nothing to show.

**Independent Test**: Register a test license service that returns a chosen license and clock, and read the info endpoint and the About dialog for each state.

**Acceptance Scenarios**:

1. **Given** a valid commercial license that ends in 200 days, **When** a signed-in user opens the About dialog, **Then** it shows the customer name, "commercial", the product tier, the support tier, the end date and 200 days left.
2. **Given** an evaluation license, **When** a signed-in user opens the About dialog, **Then** it reads "Evaluation license, N days left".
3. **Given** a license that ends while Infrahub is running, **When** the end time passes, **Then** the next read of the state reports expired, without a restart.
4. **Given** any license state, **When** a caller without sign-in reads the configuration endpoint, **Then** the response contains no license information.
5. **Given** a license that failed verification, **When** a signed-in user reads the info endpoint, **Then** the license object reports the state "invalid" with a short reason code and no license details.

---

### User Story 3 - Users are warned by a banner according to state and release (Priority: P1)

Users see a banner when the license needs attention. Who sees it and whether it can be dismissed depends on the state and on whether the running release is the first licensing release (super-admins only) or the second (every user for problems).

**Why this priority**: The banner is the only enforcement the business policy allows, so it must reach the right people and only them.

**Independent Test**: With a test license service, set each state and each release mode, sign in as a super-admin and as a regular user, and check whether the banner shows and whether it can be dismissed.

**Acceptance Scenarios**:

1. **Given** the second licensing release and no license, **When** a regular user signs in, **Then** a "running without a license" banner shows the deployment ID with a copy action, tells them to ask their Infrahub administrator for the organization's license or to contact sales, and cannot be dismissed.
2. **Given** the first licensing release and no license, **When** a regular user signs in, **Then** no banner is shown; **When** a super-admin signs in, **Then** a dismissible banner says the same and names the release in which every user will see it.
3. **Given** a license in its last 30 days, of any type, **When** a super-admin signs in, **Then** a dismissible "expires in N days" banner is shown; **When** a regular user signs in, **Then** nothing is shown.
4. **Given** a super-admin dismissed a banner, **When** they navigate within the same browser session, **Then** it stays hidden; **When** the license or its state changes, **Then** the banner shows again.
5. **Given** a browser tab left open across the moment a license ends, **When** up to an hour passes or the window regains focus, **Then** the banner updates to the expired state.
6. **Given** the info endpoint fails or returns no license object, **When** a page loads, **Then** no banner is shown.

---

### User Story 4 - API-only clients receive the license state (Priority: P2)

Customers who use Infrahub only through the REST or GraphQL API, the SDK or the MCP server receive the license state on every response once it needs attention, in the second licensing release.

**Why this priority**: The banner never reaches a customer who does not open the UI. The header is the signal the SDK and MCP follow-ups build on.

**Independent Test**: With a test license service in each state and release mode, call a REST endpoint, the GraphQL endpoint and a static asset, and inspect the response headers.

**Acceptance Scenarios**:

1. **Given** the second licensing release and an expired license, **When** a client calls a REST or GraphQL endpoint, **Then** the response carries the license status header with the value "expired".
2. **Given** the first licensing release and an expired license, **When** a client calls any endpoint, **Then** no license status header is sent.
3. **Given** a valid license, **When** a client calls any endpoint, **Then** no license status header is sent.
4. **Given** any state, **When** a client requests a static asset or a documentation page, **Then** no license status header is sent.

---

### User Story 5 - OpsMill sees each deployment's license in telemetry (Priority: P2)

The daily telemetry snapshot reports the license state and identifiers next to the deployment ID, so OpsMill can see every deployment that runs a given license, including air-gapped deployments that send their export.

**Why this priority**: It replaces deployment binding as the way OpsMill maps deployments to customers.

**Independent Test**: With a test license service, run the telemetry collection and read the stored snapshot.

**Acceptance Scenarios**:

1. **Given** a valid license, **When** the daily snapshot is collected, **Then** it contains the license state, license ID, type, product tier, support tier, start date, end date and issuer, and does not contain the customer name.
2. **Given** a deployment where no license is required, **When** the snapshot is collected, **Then** the license block is empty.
3. **Given** telemetry sending is turned off, **When** the snapshot is collected, **Then** the stored snapshot still contains the license block, so the air-gapped export includes it.

---

### User Story 6 - The upgrade command reminds operators about the license (Priority: P3)

Operators who run the upgrade command, with or without its check option, see the license state at the end of the output and what to set if a license is missing or has a problem.

**Why this priority**: Operators run this command at every upgrade, so it is where they learn to set the license before the second licensing release. It is a reminder, not a gate.

**Independent Test**: With a test license service in each state, run the upgrade command's check option and read the output and exit code.

**Acceptance Scenarios**:

1. **Given** no license in the first licensing release, **When** the operator runs the upgrade check, **Then** the output ends with "License: not set", says to set the license key on the servers and task workers, and names the release in which every user will see the banner.
2. **Given** a valid license, **When** the operator runs the upgrade check, **Then** the output ends with one line naming the customer, the type and the end date.
3. **Given** an invalid, expired or not yet valid license, **When** the operator runs the upgrade command, **Then** the output states the state, the reason and what to do, the command never prompts, and the exit code is the same as it would be without a license problem.

---

### Edge Cases

- **License ends while Infrahub runs**: the state changes at the exact end instant on the next read, without a restart.
- **Server clock is wrong**: not detected; the state follows the server clock.
- **License set on the servers but not on the task workers**: not detected; the UI shows the server's state and the telemetry snapshot, built on a task worker, shows the worker's. Each process logs its own state at startup.
- **Two API servers hold different licenses**: not detected; each request shows the state of the server that answers.
- **License service raises an unexpected error**: Infrahub keeps running; the state becomes invalid with an internal reason and an error is logged with the traceback.
- **Unknown license type or tier from a newer license format**: shown as received; an unknown type behaves like commercial.
- **Older Infrahub frontend talking to a server without the license object, or the info request fails**: no banner.
- **License key set where no license is required** (Community, or Enterprise with no license service registered): ignored and logged once, without the value.
- **Super-admin permission not yet known in the UI**: no banner meant for super-admins is shown until the permission check has answered, so regular users never see one flash.

## Requirements *(mandatory)*

### Functional Requirements

#### License data and states

- **FR-001**: The system MUST describe a license with: license ID, customer name, license type (evaluation or commercial), product tier, support tier, start instant, end instant, issue instant and issuer.
- **FR-002**: The system MUST derive exactly one state, checking in this order: not required (no license applies to this edition), unlicensed (no license supplied), invalid (a license was supplied but could not be verified), not yet valid (now is before the start), expired (now is at or after the end), expiring (now is within 30 days before the end, for every license type), valid.
- **FR-003**: The system MUST derive the state from the current time on every read, so a license that ends while Infrahub runs is reported as expired from that instant, without a restart.
- **FR-004**: The system MUST report, with each state, the days remaining before the end and the days since the end, and for invalid licenses a short reason code (malformed, bad signature, unknown key, wrong issuer, wrong product, internal error).
- **FR-005**: The system MUST accept license types and tier values it does not know, show them as received, and treat an unknown license type like commercial.

#### License service

- **FR-006**: The system MUST obtain the license state from a single license service that the Enterprise package can replace, the same way it replaces other services today.
- **FR-007**: The community default license service MUST always report "not required", and MUST report the release mode in which banners are shown to super-admins only.
- **FR-008**: The license service MUST supply the release mode (first licensing release, or second licensing release) together with the state.
- **FR-009**: The system MUST read a license key setting from the environment of every API server and task worker. When the state is "not required" (Community, or Enterprise with no license service registered), a supplied value MUST be ignored and logged once at INFO level, without the value.
- **FR-010**: A failure inside the license service MUST NOT prevent Infrahub from starting or from serving a request; it MUST result in the invalid state with the internal error reason and an error log entry with the traceback.
- **FR-011**: Each API server and task worker MUST log its license state once at startup: INFO when valid or not required, WARNING when unlicensed, not yet valid, expiring or expired, ERROR when invalid.
- **FR-012**: The license key itself MUST never appear in logs, API responses, telemetry snapshots or command output.

#### Banner rules

- **FR-013**: The system MUST decide, from the state and the release mode only, who sees a banner, whether it can be dismissed and whether the response header is sent:

  | State | First licensing release | Second licensing release | Header (second release only) |
  | --- | --- | --- | --- |
  | Not required, valid | No banner | No banner | No |
  | Expiring | Super-admins, dismissible | Super-admins, dismissible | Yes |
  | Unlicensed, invalid, not yet valid, expired | Super-admins, dismissible | Every signed-in user, not dismissible | Yes |

- **FR-014**: In the first licensing release, no response carries the license status header, whatever the state.

#### Surfaces

- **FR-015**: The signed-in info endpoint MUST return a license object with the state, the reason code, the license details (license ID, type, customer name, product tier, support tier, start, end), the days remaining, the days since expiry, the release mode, the name of the release that shows problem banners to every user (when known), and the banner decision. When no license is required it MUST return the state and no details.
- **FR-016**: The configuration endpoint, which does not require sign-in, MUST NOT return any license information.
- **FR-017**: The UI MUST show the banner decided by FR-013 on every page for signed-in users, with text per state: running without a license (with the deployment ID, a copy action, and "ask your Infrahub administrator for your organization's license, or contact sales"), license could not be verified (super-admins also see the reason), license starts on a date, license expired on a date, license expires in N days. In the first licensing release, the super-admin banner for a problem state also names the release in which every user will see it.
- **FR-018**: A dismissed banner MUST stay hidden for the rest of the browser session for the same license and state, and MUST show again when either changes.
- **FR-019**: The UI MUST refresh the license state at least hourly and whenever the window regains focus, and MUST show no banner when the license object is missing or the request fails.
- **FR-020**: The About dialog MUST show every signed-in user the customer name, license type, product tier, support tier, end date and days left; an evaluation license reads "Evaluation license, N days left".
- **FR-021**: In the second licensing release, every REST and GraphQL response MUST carry the license status header with the state when the state needs attention (FR-013); other paths, such as static assets and documentation, MUST NOT carry it.
- **FR-022**: The daily telemetry snapshot MUST include a license block with the state, license ID, license type, product tier, support tier, start, end and issuer, and MUST NOT include the customer name. The block MUST be empty when no license is required. The telemetry data format version MUST change accordingly.
- **FR-023**: The upgrade command, with and without its check option, MUST end with a license section that states the license state and, when it needs attention, what to set. It MUST print nothing about the license when no license is required, MUST NOT prompt, and MUST NOT change the exit code because of the license.

#### Dependencies

- **FR-024**: The cryptographic backend used to verify signed licenses MUST be an explicit dependency of the project rather than a transitive one, using the existing JWT library's crypto extra so that no new package is added to the dependency tree.

### Key Entities

- **License**: the verified content of a customer's license: license ID, customer name, license type, product tier, support tier, start, end, issue time, issuer. Held in memory only; never stored.
- **License status**: the state derived from a license (or its absence or failure) and the current time, with days remaining, days since expiry and, for invalid licenses, a reason code.
- **Release mode**: whether the running release is the first licensing release (banners for super-admins only, no header) or the second (banners for every user on problems, header sent).
- **Banner decision**: who sees the banner (nobody, super-admins, every signed-in user), whether it can be dismissed, and whether the response header is sent. Derived only from the license status and the release mode.
- **Telemetry license block**: the license fields included in the daily telemetry snapshot, without the customer name.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After this feature ships, Community deployments and Enterprise deployments without a production issuer show no change in behaviour: no banner, no license status header, no license section in the upgrade output, and an About dialog identical to today's. The only expected additions are the info endpoint's license object reporting "not required" and the license key setting in the configuration reference.
- **SC-002**: For every combination of the seven states, the two release modes and the two user roles (super-admin and regular user), the banner shown and its dismissibility match the banner rules in 100% of cases.
- **SC-003**: A license that reaches its end while Infrahub runs is reported as expired on the first read after the end instant, with no restart.
- **SC-004**: No failure inside the license service causes a failed startup or a failed request.
- **SC-005**: The license key never appears in any log line, API response, telemetry snapshot or command output.
- **SC-006**: An Enterprise package can replace the license service and change every surface (banner, About dialog, info endpoint, header, telemetry, upgrade output) without any further change to this repository.

## Assumptions

- The Enterprise package (opsmill/infrahub-private) supplies the real license service: reading the license key, verifying the signature offline against the accepted issuers, translating vendor fields, the daily license log, and the license command. It registers its service only once a production issuer exists, so this feature merges with no visible effect.
- The release mode is set by the Enterprise package as a constant per release, not as a setting.
- The Helm chart change that sets the license key on the servers and task workers, the install page and the upgrade guide step belong to the first licensing release, not to this feature. This feature only declares `INFRAHUB_LICENSE_KEY` as a pass-through in the shared environment of both compose files, so a key set on the host reaches the servers and task workers; Community ignores it.
- The resource-allocation telemetry change ([PR #10003](https://github.com/opsmill/infrahub/pull/10003)) lands before the telemetry data format change in this feature, so the cloud telemetry processor handles one format change at a time.
- **Release gate**: the telemetry data format change affects every deployment's snapshot, Community included. This feature may merge to the development branch, but the release that contains it ships only once the cloud telemetry processor accepts the new format.
- Super-admin means a user holding the existing super-admin global permission.
- Deployment IDs and the info endpoint already exist and are unchanged except for the added license object.

## Out of Scope

- The Enterprise license checker, the accepted issuers, signature verification, vendor field translation and the license command: opsmill/infrahub-private.
- License warnings in the Python SDK and the MCP server: follow-ups in their own repositories.
- Installing the license through the UI or a command: deferred by the design.
- Binding a license to a deployment: rejected by the design.
- Refusing to upgrade without a license: rejected by the design.
- Neo4j license acceptance in the compose file and Helm chart: separate track.
- Comparing the licensed tier with the resources a deployment uses: telemetry pipeline.
