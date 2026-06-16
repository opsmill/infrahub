import { BreadcrumbItem, Breadcrumbs } from "@infrahub/ui";

import { constructPath } from "@/shared/api/rest/fetch";

export function BreadcrumbGraphql() {
  return (
    <Breadcrumbs data-testid="breadcrumb-graphql">
      <BreadcrumbItem href={constructPath("/graphql")}>GraphQL Sandbox</BreadcrumbItem>
    </Breadcrumbs>
  );
}
