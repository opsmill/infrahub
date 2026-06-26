import { BreadcrumbItem, Breadcrumbs } from "@infrahub/ui";

import { constructPath } from "@/shared/api/rest/fetch";

export function BreadcrumbTasks() {
  return (
    <Breadcrumbs data-testid="breadcrumb-tasks">
      <BreadcrumbItem href={constructPath("/tasks")}>Tasks</BreadcrumbItem>
    </Breadcrumbs>
  );
}
