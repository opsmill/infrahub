import { describe, expect, test } from "vitest";

import type {
  LicenseFailureReason,
  LicenseInfo,
  LicenseState,
  NoticeAudience,
} from "@/entities/license/domain/model/license";
import {
  bannerText,
  invalidLicenseAdvice,
  shouldShowBanner,
} from "@/entities/license/domain/rules/license-banner";

import {
  generateLicenseInfo,
  generateLicenseInfoWithoutLicense,
} from "../../../../../tests/fake/license";

const UNLICENSED_TEXT =
  "Infrahub Enterprise is running without a license. Ask your Infrahub administrator for your organization's license, or contact sales.";
const INVALID_TEXT = "The installed license could not be verified.";
const NOT_YET_VALID_TEXT = "The installed license starts on 2027-10-01.";
const EXPIRED_TEXT =
  "Your Infrahub Enterprise license expired on 2027-09-29. Contact sales to renew.";
const EXPIRING_TEXT = "Your license expires in 12 days, on 2027-09-29.";
const CHECK_KEY_TEXT = "Check INFRAHUB_LICENSE_KEY on the servers and task workers.";

const formatUtcDay = (date: Date) => date.toISOString().slice(0, 10);

function licenseInState(state: LicenseState, overrides: Partial<LicenseInfo> = {}) {
  switch (state) {
    case "not_required":
    case "unlicensed":
      return generateLicenseInfoWithoutLicense({ state, ...overrides });
    case "invalid":
      return generateLicenseInfoWithoutLicense({ state, reason: "bad_signature", ...overrides });
    case "not_yet_valid":
      return generateLicenseInfo({
        state,
        starts_at: "2027-10-01T00:00:00Z",
        ends_at: "2028-10-01T00:00:00Z",
        days_remaining: 365,
        ...overrides,
      });
    case "expired":
      return generateLicenseInfo({
        state,
        days_remaining: null,
        days_since_expiry: 4,
        ...overrides,
      });
    case "expiring":
      return generateLicenseInfo({ state, days_remaining: 12, ...overrides });
    case "valid":
      return generateLicenseInfo({ state, ...overrides });
  }
}

function shownToAllUsersWhenEnforced(enforcingRelease: string | null): Partial<LicenseInfo> {
  return {
    notice_mode: "quiet",
    enforcing_release: enforcingRelease,
    banner: { audience: "super_admins", dismissible: true, shown_to_all_users_when_enforced: true },
  };
}

describe("shouldShowBanner", () => {
  test.each<{
    audience: NoticeAudience;
    isSuperAdmin: boolean;
    permissionResolved: boolean;
    expected: boolean;
  }>([
    { audience: "all_users", isSuperAdmin: false, permissionResolved: true, expected: true },
    { audience: "all_users", isSuperAdmin: true, permissionResolved: true, expected: true },
    { audience: "all_users", isSuperAdmin: false, permissionResolved: false, expected: true },
    { audience: "super_admins", isSuperAdmin: true, permissionResolved: true, expected: true },
    { audience: "super_admins", isSuperAdmin: false, permissionResolved: true, expected: false },
    { audience: "super_admins", isSuperAdmin: false, permissionResolved: false, expected: false },
    { audience: "super_admins", isSuperAdmin: true, permissionResolved: false, expected: false },
    { audience: "none", isSuperAdmin: true, permissionResolved: true, expected: false },
    { audience: "none", isSuperAdmin: false, permissionResolved: true, expected: false },
  ])(
    "returns $expected for $audience when isSuperAdmin=$isSuperAdmin and permissionResolved=$permissionResolved",
    ({ audience, isSuperAdmin, permissionResolved, expected }) => {
      // GIVEN
      const viewer = { isSuperAdmin, permissionResolved };

      // WHEN
      const result = shouldShowBanner(audience, viewer.isSuperAdmin, viewer.permissionResolved);

      // THEN
      expect(result).toBe(expected);
    }
  );
});

describe("bannerText", () => {
  test.each<{ state: LicenseState; expected: string | null }>([
    { state: "unlicensed", expected: UNLICENSED_TEXT },
    { state: "invalid", expected: INVALID_TEXT },
    { state: "not_yet_valid", expected: NOT_YET_VALID_TEXT },
    { state: "expired", expected: EXPIRED_TEXT },
    { state: "expiring", expected: EXPIRING_TEXT },
    { state: "valid", expected: null },
    { state: "not_required", expected: null },
  ])("reads the $state text", ({ state, expected }) => {
    // GIVEN
    const license = licenseInState(state, { enforcing_release: "1.13" });

    // WHEN
    const result = bannerText(license, formatUtcDay);

    // THEN
    expect(result).toBe(expected);
  });

  test.each<{ state: LicenseState; text: string }>([
    { state: "unlicensed", text: UNLICENSED_TEXT },
    { state: "invalid", text: INVALID_TEXT },
    { state: "not_yet_valid", text: NOT_YET_VALID_TEXT },
    { state: "expired", text: EXPIRED_TEXT },
  ])(
    "names the enforcing release after the $state text when every user will see the banner",
    ({ state, text }) => {
      // GIVEN
      const license = licenseInState(state, shownToAllUsersWhenEnforced("1.13"));

      // WHEN
      const result = bannerText(license, formatUtcDay);

      // THEN
      expect(result).toBe(`${text} From Infrahub 1.13, this is shown to all users.`);
    }
  );

  test.each<{ state: LicenseState; text: string }>([
    { state: "unlicensed", text: UNLICENSED_TEXT },
    { state: "invalid", text: INVALID_TEXT },
    { state: "not_yet_valid", text: NOT_YET_VALID_TEXT },
    { state: "expired", text: EXPIRED_TEXT },
  ])(
    "announces a future release after the $state text when no enforcing release is named",
    ({ state, text }) => {
      // GIVEN
      const license = licenseInState(state, shownToAllUsersWhenEnforced(null));

      // WHEN
      const result = bannerText(license, formatUtcDay);

      // THEN
      expect(result).toBe(`${text} In a future release, this will be shown to all users.`);
    }
  );

  test("adds no release note when the banner stays limited to super-admins", () => {
    // GIVEN
    const license = licenseInState("invalid", {
      reason: "internal_error",
      notice_mode: "quiet",
      enforcing_release: "1.13",
      banner: {
        audience: "super_admins",
        dismissible: true,
        shown_to_all_users_when_enforced: false,
      },
    });

    // WHEN
    const result = bannerText(license, formatUtcDay);

    // THEN
    expect(result).toBe(INVALID_TEXT);
  });

  test("uses the singular for a single day left", () => {
    // GIVEN
    const license = licenseInState("expiring", { days_remaining: 1 });

    // WHEN
    const result = bannerText(license, formatUtcDay);

    // THEN
    expect(result).toBe("Your license expires in 1 day, on 2027-09-29.");
  });

  test("shows the end date as the last day the license covers", () => {
    // GIVEN
    const license = licenseInState("expired", {
      ends_at: "2027-03-01T00:00:00Z",
      days_since_expiry: 0,
    });

    // WHEN
    const result = bannerText(license, formatUtcDay);

    // THEN
    expect(result).toBe(
      "Your Infrahub Enterprise license expired on 2027-02-28. Contact sales to renew."
    );
  });

  test("formats dates with the given day formatter", () => {
    // GIVEN
    const license = licenseInState("not_yet_valid");

    // WHEN
    const result = bannerText(license, () => "1 October 2027");

    // THEN
    expect(result).toBe("The installed license starts on 1 October 2027.");
  });
});

describe("invalidLicenseAdvice", () => {
  test.each<{ reason: LicenseFailureReason; explanation: string }>([
    { reason: "malformed", explanation: "The license key is not a well-formed license." },
    { reason: "bad_signature", explanation: "The license signature does not match its content." },
    {
      reason: "unknown_key",
      explanation: "The license is signed with a key this release does not recognize.",
    },
    {
      reason: "wrong_issuer",
      explanation: "The license comes from an issuer this release does not accept.",
    },
    { reason: "wrong_product", explanation: "The license is for a different product." },
  ])("explains $reason and points to the license key setting", ({ reason, explanation }) => {
    // GIVEN
    const failureReason = reason;

    // WHEN
    const result = invalidLicenseAdvice(failureReason);

    // THEN
    expect(result).toBe(`${explanation} ${CHECK_KEY_TEXT}`);
  });

  test("points an internal error to the server logs rather than the license key", () => {
    // GIVEN
    const failureReason = "internal_error";

    // WHEN
    const result = invalidLicenseAdvice(failureReason);

    // THEN
    expect(result).toBe(
      "The license state could not be determined because of an internal error. Check the server logs."
    );
  });

  test("points to the license key setting when no reason is given", () => {
    // GIVEN
    const failureReason = null;

    // WHEN
    const result = invalidLicenseAdvice(failureReason);

    // THEN
    expect(result).toBe(CHECK_KEY_TEXT);
  });
});
