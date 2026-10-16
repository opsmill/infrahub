# Contract: `GET /api/info` license object

`/api/info` requires sign-in (unchanged). It gains a `license` object. `GET /api/config`, which does not require sign-in, is unchanged and carries no license information.

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
    "banner": { "audience": "super_admins", "dismissible": true }
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
    "banner": { "audience": "none", "dismissible": false }
  }
}
```

## Rules

- License detail fields are `null` unless the status carries a license (states `not_yet_valid`, `expired`, `expiring`, `valid`).
- `reason` is a short code and reveals nothing secret; the UI shows its explanation to super-admins only.
- The key itself is never part of the response.
- If computing the status raises, the endpoint still answers with `state: "invalid"`, `reason: "internal_error"`.
- `schema/openapi.json` and `frontend/app/src/shared/api/rest/types.generated.ts` are regenerated.
