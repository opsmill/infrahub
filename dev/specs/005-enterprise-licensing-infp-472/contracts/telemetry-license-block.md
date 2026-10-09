# Contract: telemetry license block

The daily snapshot (`TelemetryData`) gains a `license` field. `TELEMETRY_VERSION` (the snapshot `payload_format`) is bumped.

```jsonc
// Today
{ "deployment_id": "1f0a...", "infrahub_type": "enterprise", ... }

// After, a license is required
{
  "deployment_id": "1f0a...",
  "infrahub_type": "enterprise",
  "license": {
    "state": "valid",
    "license_id": "f67dea44-...",
    "license_type": "commercial",
    "product_tier": "medium",
    "support_tier": "advanced",
    "starts_at": "2026-09-30T00:00:00Z",
    "ends_at": "2027-09-30T00:00:00Z",
    "issuer": "<issuer>"
  },
  ...
}

// After, no license required (Community, or Enterprise with no license service registered)
{ "deployment_id": "1f0a...", "infrahub_type": "community", "license": null, ... }
```

## Rules

- The customer name is never included.
- For `unlicensed` and `invalid`, only `state` is set; the other fields are `null`.
- The block is built on the task worker, from the task worker's license service.
- The snapshot is stored locally whether or not sending is turned off, so the air-gapped export carries the block.
- A failure while building the block is logged and stores `license: null` rather than failing the snapshot.
