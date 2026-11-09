import { BreadcrumbItem, Breadcrumbs } from "@infrahub/ui";

import { constructPath } from "@/shared/api/rest/fetch";

export function BreadcrumbGlobalPreferences() {
  return (
    <Breadcrumbs data-testid="breadcrumb-global-preferences">
      <BreadcrumbItem href={constructPath("/global-preferences")}>
        Global preferences
      </BreadcrumbItem>
    </Breadcrumbs>
  );
}
