import { Button } from "@infrahub/ui";
import { TriangleAlertIcon, XIcon } from "lucide-react";

import { CopyToClipboardButton } from "@/shared/components/buttons/copy-to-clipboard-button";
import { Col, Row } from "@/shared/components/container";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { useGetAppInfo } from "@/entities/config/ui/queries/get-app-info.query";
import type { LicenseInfo } from "@/entities/license/domain/model/license";
import {
  bannerText,
  invalidLicenseAdvice,
  shouldShowBanner,
} from "@/entities/license/domain/rules/license-banner";
import { useFormatLicenseDay } from "@/entities/license/ui/hooks/use-format-license-day";
import { useLicenseBannerDismissal } from "@/entities/license/ui/hooks/use-license-banner-dismissal";
import { SUPER_ADMIN } from "@/entities/permission/domain/model/permission";
import { useHasGlobalPermission } from "@/entities/permission/ui/queries/has-global-permission.query";

export function LicenseBanner() {
  const { isAuthenticated } = useAuth();
  const { data, isError } = useGetAppInfo();
  const license = data?.license;

  // A sign-out in another tab leaves the signed-in answer cached, and the license is for signed-in users only.
  if (!isAuthenticated) {
    return null;
  }

  // Stops here when no banner applies, so the permission check runs only when one may show.
  if (isError || !data || !license || license.banner.audience === "none") {
    return null;
  }

  return <LicenseNotice license={license} deploymentId={data.deployment_id} />;
}

interface LicenseNoticeProps {
  license: LicenseInfo;
  deploymentId: string;
}

function LicenseNotice({ license, deploymentId }: LicenseNoticeProps) {
  const { data: isSuperAdmin = false, isSuccess: isPermissionResolved } =
    useHasGlobalPermission(SUPER_ADMIN);
  const { isDismissed, dismiss } = useLicenseBannerDismissal(license);
  const formatLicenseDay = useFormatLicenseDay();

  const { audience, dismissible } = license.banner;
  const text = bannerText(license, formatLicenseDay);

  if (
    text === null ||
    !shouldShowBanner(audience, isSuperAdmin, isPermissionResolved) ||
    (dismissible && isDismissed)
  ) {
    return null;
  }

  const showsFailureReason = license.state === "invalid" && isPermissionResolved && isSuperAdmin;

  return (
    <section
      aria-label="License notice"
      className="flex shrink-0 items-start gap-2 rounded-2xl border border-warning-border bg-warning-surface px-3 py-2 text-foreground text-sm"
    >
      <TriangleAlertIcon className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true" />

      <Col className="flex-1 gap-1">
        <p>{text}</p>

        {showsFailureReason && <p>{invalidLicenseAdvice(license.reason)}</p>}

        {license.state === "unlicensed" && (
          <Row className="gap-1">
            <span>Deployment ID: {deploymentId}</span>
            <CopyToClipboardButton data={deploymentId} aria-label="Copy deployment ID" />
          </Row>
        )}
      </Col>

      {dismissible && (
        <Button
          variant="ghost"
          size="xs"
          shape="square"
          className="-my-1"
          aria-label="Dismiss license notice"
          onPress={dismiss}
        >
          <XIcon />
        </Button>
      )}
    </section>
  );
}
