import { constructPath } from "@/shared/api/rest/fetch";
import { Breadcrumb, BreadcrumbItem } from "@/shared/components/ui/breadcrumb";

export function BreadcrumbSchema() {
  return (
    <Breadcrumb data-testid="breadcrumb-schema">
      <BreadcrumbItem href={constructPath("/schema")}>Schema</BreadcrumbItem>
    </Breadcrumb>
  );
}
