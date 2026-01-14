import { Card } from "@/shared/components/ui/card";

import BranchSelector from "@/entities/branches/ui/branch-selector";
import { BreadcrumbNavigation } from "@/entities/navigation/ui/breadcrumbs/breadcrumb-navigation";
import { TimeFrameSelector } from "@/entities/navigation/ui/time-selector";
import { TaskStatus } from "@/entities/tasks/ui/task-status";

export function AppHeader() {
  return (
    <Card className="flex h-12.5 items-center gap-2 p-2">
      <TimeFrameSelector />

      <BranchSelector />

      <div className="flex-1" data-testid="breadcrumb-navigation">
        <BreadcrumbNavigation />
      </div>

      <TaskStatus />
    </Card>
  );
}
