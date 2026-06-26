# Quickstart — Auto-create Account Groups (INFP-556)

This quickstart walks an admin through enabling the feature, observing it on a first login, and verifying the audit trail. It is the same scenario that backs User Story 1's Independent Test in `spec.md`.

## Prerequisites

- Infrahub 1.10 instance (the schema definition update adds the optional `origin` attribute; no data backfill runs — see `contracts/schema-delta.md`).
- At least one configured SSO/OIDC/OAuth2 provider, or native LDAP (INFP-105) for the LDAP path.
- A test user in the external IdP carrying at least one group claim that you control.

## 1 — Configure the filter

Set the regex filter env var on the Infrahub backend. The presence of a non-empty filter is the sole activation surface for auto-creation (FR-001, no separate enable toggle).

```bash
export INFRAHUB_SECURITY_AUTO_CREATE_GROUPS_FILTER='^LDAP/group/(?P<name>.+)$'
# Optional: tighten the per-login soft cap (default 50)
export INFRAHUB_SECURITY_AUTO_CREATE_GROUPS_MAX_PER_LOGIN=20
```

Restart the backend. If the regex is invalid, startup fails loudly with the setting name and the parser error (FR-004); fix and restart.

## 2 — Verify the feature is on without any side-effect yet

Before any login, the local `CoreAccountGroup` list is unchanged. Confirm via API or UI that no new groups were auto-created merely by enabling the filter.

## 3 — Trigger the first login

Log in as your test user. Their external claim set must include at least one claim matching the filter — e.g., `LDAP/group/network-engineering`.

Expected:

- The login completes successfully.
- A `CoreAccountGroup` named `network-engineering` (the captured name) now exists.
- Its `origin` attribute is set to the **configured name** of the identity provider you logged in through (e.g., the value of the `name` field on your OIDC provider config — `"AzureAD-corp"`, `"OktaProd"`, etc., or the configured LDAP provider name). The value is the same string as is recorded on the auto-creation event's `idp` field. Note: `origin` uses `display: extra` — it is hidden from the default group detail view but appears when you toggle on the extra/advanced-attributes view; via the API (GraphQL/REST) it is always queryable.
- The test user is a member of that group.
- The group has zero attached roles and zero attached permissions (auto-created groups land empty by design — FR-009).

Independently, query a manually-created or platform-seeded `CoreAccountGroup` via the API and confirm its `origin` attribute is **unset** (null/absent). Only the auto-creation path writes a value (FR-013, clarification 2026-05-13).

## 4 — Verify provenance & idempotency

Log a second different user in carrying the same external `LDAP/group/network-engineering` claim.

Expected:

- No new `CoreAccountGroup` is created; the existing one is reused (FR-018).
- The second user is added as a member.
- No new `GroupAutoCreatedEvent` is emitted for this second login (FR-015 acceptance scenario 2).

## 5 — Inspect the audit trail

Query the activity event log filtered to `GroupAutoCreatedEvent` for the first login. Expected payload fields:

- `group_name = "network-engineering"`
- `source_pattern = "^LDAP/group/(?P<name>.+)$"`
- `idp` = the **configured name** of the identity provider that authenticated the login (e.g., `"AzureAD-corp"`, `"OktaProd"`, `"corp-ldap"`) — same string as `origin` on the new group
- `triggering_user_id` + `triggering_user_name` = the first test user
- `origin_value` = the same value as the group's `origin` attribute (and as `idp`)

## 6 — Verify filter scoping (negative path)

Log in another test user whose claims include unrelated groups (e.g., `slack/general`, `github/contributors`). Confirm:

- The login succeeds.
- No `CoreAccountGroup` named `slack/general` or `github/contributors` was created.
- If you configured `sso_user_default_group` (IFC-922) and the user has zero matching claims, they are added to the default group; if they had at least one matching claim, the default group is NOT stacked on top (FR-016).

## 7 — Verify `origin` read-only enforcement

Attempt to modify the `origin` attribute on the auto-created group via:

- The UI form for that group → toggle on the extra/advanced-attributes view so `origin` is rendered; the field MUST be presented as read-only (no editable input) per FR-021. If somehow surfaced as editable via developer tooling, the save MUST still reject.
- A GraphQL mutation setting `origin` → expect a validation error, OR the field is silently ignored.
- A REST PATCH/PUT → same.
- A schema-load that includes a manual `origin` value → same.

In every case, the existing `origin` value MUST be preserved (FR-021).

Also attempt to *set* an initial `origin` value on a manually-created group via the same four surfaces — every attempt MUST be rejected/ignored, and the group's `origin` MUST remain unset (FR-013, FR-021).

## 8 — Verify the cap (only if you can simulate many claims)

Configure a user carrying more matching claims than the per-login cap (default 50; or set the cap low for the test). On login:

- Up to `cap` new groups are created.
- The login succeeds.
- One `GroupAutoCreateCappedEvent` is emitted, carrying `cap_value`, `dropped_count`, and `dropped_claims` (verbatim, length-truncated). See `contracts/events.md`.

## 9 — Turn the feature off

```bash
unset INFRAHUB_SECURITY_AUTO_CREATE_GROUPS_FILTER
```

Restart. Auto-creation is now inactive. Existing auto-created groups remain (lifecycle/cleanup is INFP-536, explicitly out of scope here). The IFC-922 default-group fallback continues to apply unchanged.
