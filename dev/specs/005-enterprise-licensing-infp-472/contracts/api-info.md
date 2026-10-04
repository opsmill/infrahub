# Contract: `GET /api/info` license object

`/api/info` answers anonymous `GET` requests when `main.allow_anonymous_access` is on, which is the default. It gains a `license` field: the license object for a signed-in session, `null` for an anonymous one. `GET /api/config`, which does not require sign-in, is unchanged and carries no license information.

## Response

```jsonc
// Today
{ "deployment_id": "1f0a...", "version": "1.12.0" }

// After: a license is required and present
{
  "deployment_id": "1f0a...",
  "version": "1.12.0",
  "license": {
    "state": "expiring",               // LicenseState
    "reason": null,                    // LicenseFailureReason, only when state == "invalid"
    "license_id": "f67dea44-...",
    "license_type": "commercial",
    "customer_name": "ACME Test Ltd",
    "product_tier": "medium",
    "support_tier": "advanced",
    "starts_at": "2026-09-30T00:00:00Z",
    "ends_at": "2027-09-30T00:00:00Z",
    "days_remaining": 12,
    "days_since_expiry": null,
    "notice_mode": "quiet",
    "enforcing_release": null,
    "banner": { "audience": "super_admins", "dismissible": true, "shown_to_all_users_when_enforced": false }
  }
}

// After: Community, or Enterprise with no license service registered
{
  "deployment_id": "1f0a...",
  "version": "1.12.0",
  "license": {
    "state": "not_required", "reason": null,
    "license_id": null, "license_type": null, "customer_name": null,
    "product_tier": null, "support_tier": null, "starts_at": null, "ends_at": null,
    "days_remaining": null, "days_since_expiry": null,
    "notice_mode": "quiet", "enforcing_release": null,
    "banner": { "audience": "none", "dismissible": false, "shown_to_all_users_when_enforced": false }
  }
}

// After: an anonymous caller, whatever the license state
{
  "deployment_id": "1f0a...",
  "version": "1.12.0",
  "license": null
}
```

## Rules

- License detail fields are `null` unless the status carries a license (states `not_yet_valid`, `expired`, `expiring`, `valid`).
- `license` is `null` for an anonymous caller, in every state, so a visitor who is not signed in never gets the license details or the failure reason from this endpoint. In the enforcing release, the response header ([response-header.md](response-header.md)) is the one deliberate place where any caller, signed in or not, sees the state. The field is always present; a license object, when present, always carries its details.
- `reason` is a short code and reveals nothing secret; the UI shows its explanation to super-admins only.
- `banner.shown_to_all_users_when_enforced` is true when only super-admins see the banner now and every user sees it in the enforcing release: `notice_mode` is `quiet` and the enforce-mode audience for the status is `all_users`. The server decides it, so the UI holds no copy of the notice rules.
- `invalid` with `internal_error` gets `banner: { "audience": "super_admins", "dismissible": true, "shown_to_all_users_when_enforced": false }` in both modes. An internal error is a defect in Infrahub, not in the customer's license, so it never reaches every user.
- The key itself is never part of the response.
- If computing the status raises, the endpoint still answers with `state: "invalid"`, `reason: "internal_error"`.
- `schema/openapi.json` and `frontend/app/src/shared/api/rest/types.generated.ts` are regenerated.
