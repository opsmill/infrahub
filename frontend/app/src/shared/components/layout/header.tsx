import BranchSelector from "@/shared/components/branch-selector";
import BreadcrumbNavigation from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-navigation";
import { TimeFrameSelector } from "@/shared/components/time-selector";
import { Card } from "@/shared/components/ui/card";

import { TaskStatus } from "@/entities/tasks/ui/task-status";

export default function Header() {
  return (
    <Card className="flex h-12.5 items-center gap-2 p-2">
      <TimeFrameSelector />

      <BranchSelector />

      <div className="flex-1">
        <BreadcrumbNavigation />
      </div>

      <TaskStatus />
    </Card>
  );
}
