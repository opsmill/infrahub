import type { LicenseInfo } from "@/entities/license/domain/model/license";

export const generateLicenseInfo = (overrides?: Partial<LicenseInfo>): LicenseInfo => {
  return {
    state: "valid",
    reason: null,
    license_id: "f67dea44-7d3b-4c1e-9a52-1b0f3c2d4e5f",
    license_type: "commercial",
    customer_name: "ACME Test Ltd",
    product_tier: "medium",
    support_tier: "advanced",
    starts_at: "2026-09-30T00:00:00Z",
    ends_at: "2027-09-30T00:00:00Z",
    days_remaining: 200,
    days_since_expiry: null,
    notice_mode: "quiet",
    enforcing_release: null,
    banner: { audience: "none", dismissible: false },
    ...overrides,
  };
};

export const generateLicenseInfoWithoutLicense = (
  overrides?: Partial<LicenseInfo>
): LicenseInfo => {
  return generateLicenseInfo({
    state: "not_required",
    license_id: null,
    license_type: null,
    customer_name: null,
    product_tier: null,
    support_tier: null,
    starts_at: null,
    ends_at: null,
    days_remaining: null,
    ...overrides,
  });
};
