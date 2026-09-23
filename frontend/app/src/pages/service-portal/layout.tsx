import { Outlet } from "react-router";

import { ServicePortalLayout } from "@/entities/service-portal/ui/service-portal-layout";

export function Component() {
  return (
    <ServicePortalLayout>
      <Outlet />
    </ServicePortalLayout>
  );
}
