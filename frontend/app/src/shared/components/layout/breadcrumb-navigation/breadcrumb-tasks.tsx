import { constructPath } from "@/shared/api/rest/fetch";
import { Breadcrumb, BreadcrumbItem } from "@/shared/components/ui/breadcrumb";

export function BreadcrumbTasks() {
  return (
    <Breadcrumb data-testid="breadcrumb-tasks">
      <BreadcrumbItem href={constructPath("/tasks")}>Tasks</BreadcrumbItem>
    </Breadcrumb>
  );
}
