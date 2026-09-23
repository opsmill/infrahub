import { Card, LinkButton } from "@infrahub/ui";
import { ArrowLeftIcon } from "lucide-react";
import { Link } from "react-router";

import InfrahubWithTextLogo from "@/assets/Infrahub-SVG-hori.svg";

import { focusVisibleStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import { SERVICE_PORTAL_URL } from "@/entities/service-portal/ui/routing/service-portal-urls";
import { AccountMenu } from "@/entities/user-profile/ui/account-menu";

// No branch selector on purpose: the portal always works on the default branch.
export function ServicePortalHeader() {
  return (
    <Card className="h-12.5 shrink-0 flex-row items-center gap-2 p-2">
      <Link
        to={SERVICE_PORTAL_URL}
        aria-label="Service portal home"
        className={classNames(focusVisibleStyle, "flex items-center gap-2 rounded-md")}
      >
        <img src={InfrahubWithTextLogo} alt="Infrahub" className="h-8" />
        <span className="font-medium text-neutral-700 text-sm">Service portal</span>
      </Link>

      <nav aria-label="Service portal" className="flex flex-1 items-center gap-1">
        <LinkButton variant="ghost" size="sm" href={SERVICE_PORTAL_URL}>
          Catalog
        </LinkButton>
      </nav>

      <LinkButton variant="ghost" size="sm" href="/">
        <ArrowLeftIcon /> Back to Infrahub
      </LinkButton>

      <AccountMenu />
    </Card>
  );
}
