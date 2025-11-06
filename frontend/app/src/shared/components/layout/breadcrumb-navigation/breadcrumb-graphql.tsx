import { constructPath } from "@/shared/api/rest/fetch";
import { Breadcrumb, BreadcrumbItem } from "@/shared/components/ui/breadcrumb";

export function BreadcrumbGraphql() {
  return (
    <Breadcrumb data-testid="breadcrumb-graphql">
      <BreadcrumbItem href={constructPath("/graphql")}>GraphQL Sandbox</BreadcrumbItem>
    </Breadcrumb>
  );
}
