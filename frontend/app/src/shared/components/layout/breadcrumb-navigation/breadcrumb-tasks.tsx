import { constructPath } from "@/shared/api/rest/fetch";
import { BreadcrumbItem, Breadcrumbs } from "@/shared/components/aria/breadcrumbs";

export function BreadcrumbTasks() {
  return (
    <Breadcrumbs data-testid="breadcrumb-tasks">
      <BreadcrumbItem href={constructPath("/tasks")}>Tasks</BreadcrumbItem>
    </Breadcrumbs>
  );
}
