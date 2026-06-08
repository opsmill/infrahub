import { BreadcrumbItem, Breadcrumbs } from "@infrahub/ui";

import { constructPath } from "@/shared/api/rest/fetch";

export function BreadcrumbAccountProfile() {
  return (
    <Breadcrumbs data-testid="breadcrumb-profile">
      <BreadcrumbItem href={constructPath("/profile")}>Account settings</BreadcrumbItem>
    </Breadcrumbs>
  );
}
