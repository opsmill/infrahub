import { constructPath } from "@/shared/api/rest/fetch";
import { Breadcrumb, BreadcrumbItem } from "@/shared/components/ui/breadcrumb";

export function BreadcrumbProfile() {
  return (
    <Breadcrumb data-testid="breadcrumb-profile">
      <BreadcrumbItem href={constructPath("/profile")}>Account settings</BreadcrumbItem>
    </Breadcrumb>
  );
}
