import { constructPath } from "@/shared/api/rest/fetch";
import { BreadcrumbItem, Breadcrumbs } from "@/shared/components/aria/breadcrumbs";

export function BreadcrumbAccountProfile() {
  return (
    <Breadcrumbs data-testid="breadcrumb-profile">
      <BreadcrumbItem href={constructPath("/profile")}>Account settings</BreadcrumbItem>
    </Breadcrumbs>
  );
}
