import { pluralize } from "@/shared/utils/string";

import type {
  LicenseFailureReason,
  LicenseInfo,
  NoticeAudience,
} from "@/entities/license/domain/model/license";
import { lastCoveredDay } from "@/entities/license/domain/rules/license-dates";

type FormatDay = (date: Date) => string;

const CHECK_LICENSE_KEY = "Check INFRAHUB_LICENSE_KEY on the servers and task workers.";

const FAILURE_REASON_ADVICE: Record<LicenseFailureReason, string> = {
  malformed: `The license key is not a well-formed license. ${CHECK_LICENSE_KEY}`,
  bad_signature: `The license signature does not match its content. ${CHECK_LICENSE_KEY}`,
  unknown_key: `The license is signed with a key this release does not recognize. ${CHECK_LICENSE_KEY}`,
  wrong_issuer: `The license comes from an issuer this release does not accept. ${CHECK_LICENSE_KEY}`,
  wrong_product: `The license is for a different product. ${CHECK_LICENSE_KEY}`,
  internal_error:
    "The license state could not be determined because of an internal error. Check the server logs.",
};

/** A super-admin banner stays hidden until the permission check has answered, so a regular user never sees it flash. */
export function shouldShowBanner(
  audience: NoticeAudience,
  isSuperAdmin: boolean,
  permissionResolved: boolean
): boolean {
  switch (audience) {
    case "all_users":
      return true;
    case "super_admins":
      return permissionResolved && isSuperAdmin;
    case "none":
      return false;
  }
}

/** Returns the banner text for the license state, or `null` when the state has no banner. */
export function bannerText(license: LicenseInfo, formatDay: FormatDay): string | null {
  const message = stateMessage(license, formatDay);
  if (message === null || !license.banner.shown_to_all_users_when_enforced) {
    return message;
  }

  return `${message} ${enforcingReleaseNote(license.enforcing_release)}`;
}

export function invalidLicenseAdvice(reason: LicenseFailureReason | null): string {
  return reason === null ? CHECK_LICENSE_KEY : FAILURE_REASON_ADVICE[reason];
}

function stateMessage(license: LicenseInfo, formatDay: FormatDay): string | null {
  const { state, starts_at, ends_at, days_remaining } = license;

  switch (state) {
    case "unlicensed":
      return "Infrahub Enterprise is running without a license. Ask your Infrahub administrator for your organization's license, or contact sales.";
    case "invalid":
      return "The installed license could not be verified.";
    case "not_yet_valid":
      return starts_at === null
        ? null
        : `The installed license starts on ${formatDay(new Date(starts_at))}.`;
    case "expired":
      return ends_at === null
        ? null
        : `Your Infrahub Enterprise license expired on ${formatDay(lastCoveredDay(ends_at))}. Contact sales to renew.`;
    case "expiring":
      return ends_at === null || days_remaining === null
        ? null
        : `Your license expires in ${pluralize(days_remaining, "day")}, on ${formatDay(lastCoveredDay(ends_at))}.`;
    case "not_required":
    case "valid":
      return null;
  }
}

function enforcingReleaseNote(enforcingRelease: string | null): string {
  return enforcingRelease === null
    ? "In a future release, this will be shown to all users."
    : `From Infrahub ${enforcingRelease}, this is shown to all users.`;
}
