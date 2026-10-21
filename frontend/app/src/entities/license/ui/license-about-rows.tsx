import { Separator } from "@/shared/components/aria/separator";
import { InfoRow } from "@/shared/components/display/info-row";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import type { LicenseInfo } from "@/entities/license/domain/model/license";
import { lastCoveredDay } from "@/entities/license/domain/rules/license-dates";
import { useFormatLicenseDay } from "@/entities/license/ui/hooks/use-format-license-day";

interface LicenseAboutRowsProps {
  license: LicenseInfo | null | undefined;
}

export function LicenseAboutRows({ license }: LicenseAboutRowsProps) {
  const { isAuthenticated } = useAuth();

  // The About dialog is also open to anonymous visitors, and the license is for signed-in users only.
  if (!isAuthenticated || !license) {
    return null;
  }

  switch (license.state) {
    case "not_required":
      return null;
    case "unlicensed":
      return <LicenseRow label="License" value="Not installed" />;
    case "invalid":
      return <LicenseRow label="License" value="Could not be verified" />;
    case "not_yet_valid":
    case "expired":
    case "expiring":
    case "valid":
      return <HeldLicenseRows license={license} />;
  }
}

function HeldLicenseRows({ license }: { license: LicenseInfo }) {
  const formatLicenseDay = useFormatLicenseDay();
  const starts =
    license.starts_at === null ? null : `${formatLicenseDay(license.starts_at)} (not valid yet)`;
  const ends =
    license.ends_at === null
      ? null
      : `${formatLicenseDay(lastCoveredDay(license.ends_at))} (${timeLeftText(license)})`;

  return (
    <>
      <LicenseRow label="License" value={license.customer_name} />
      <LicenseRow label="Type" value={licenseTypeText(license)} />
      <LicenseRow label="Product tier" value={license.product_tier} />
      <LicenseRow label="Support tier" value={license.support_tier} />
      {license.state === "not_yet_valid" && <LicenseRow label="Starts" value={starts} />}
      <LicenseRow label="Ends" value={ends} />
    </>
  );
}

function LicenseRow({ label, value }: { label: string; value: string | null }) {
  return (
    <>
      <Separator />
      <InfoRow label={label} value={value} />
    </>
  );
}

function licenseTypeText({ license_type, days_remaining }: LicenseInfo) {
  if (license_type !== "evaluation") {
    return "Commercial";
  }
  return days_remaining === null
    ? "Evaluation license"
    : `Evaluation license, ${dayCount(days_remaining)} left`;
}

function timeLeftText({ days_remaining, days_since_expiry }: LicenseInfo) {
  if (days_remaining !== null) {
    return `${dayCount(days_remaining)} left`;
  }
  const daysExpired = days_since_expiry ?? 0;
  if (daysExpired === 0) {
    return "expired today";
  }
  return `expired ${dayCount(daysExpired)} ago`;
}

function dayCount(count: number) {
  return `${count} ${count === 1 ? "day" : "days"}`;
}
