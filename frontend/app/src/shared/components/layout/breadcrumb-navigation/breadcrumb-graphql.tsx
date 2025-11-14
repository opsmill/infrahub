import { constructPath } from "@/shared/api/rest/fetch";
import { BreadcrumbItem, Breadcrumbs } from "@/shared/components/aria/breadcrumbs";

export function BreadcrumbGraphql() {
  return (
    <Breadcrumbs data-testid="breadcrumb-graphql">
      <BreadcrumbItem href={constructPath("/graphql")}>GraphQL Sandbox</BreadcrumbItem>
    </Breadcrumbs>
  );
}
