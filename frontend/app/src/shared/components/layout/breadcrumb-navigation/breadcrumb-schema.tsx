import { constructPath } from "@/shared/api/rest/fetch";
import { BreadcrumbItem, Breadcrumbs } from "@/shared/components/aria/breadcrumbs";

export function BreadcrumbSchema() {
  return (
    <Breadcrumbs data-testid="breadcrumb-schema">
      <BreadcrumbItem href={constructPath("/schema")}>Schema</BreadcrumbItem>
    </Breadcrumbs>
  );
}
