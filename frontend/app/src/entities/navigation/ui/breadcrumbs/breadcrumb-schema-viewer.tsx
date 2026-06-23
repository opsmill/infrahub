import { BreadcrumbItem, Breadcrumbs } from "@infrahub/ui";

import { constructPath } from "@/shared/api/rest/fetch";

export function BreadcrumbSchemaViewer() {
  return (
    <Breadcrumbs data-testid="breadcrumb-schema">
      <BreadcrumbItem href={constructPath("/schema")}>Schema</BreadcrumbItem>
    </Breadcrumbs>
  );
}
