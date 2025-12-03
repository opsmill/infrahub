import BranchSelector from "@/shared/components/branch-selector";
import { TimeFrameSelector } from "@/shared/components/time-selector";
import { Card } from "@/shared/components/ui/card";

import { BreadcrumbNavigation } from "@/entities/navigation/ui/breadcrumbs/breadcrumb-navigation";
import { TaskStatus } from "@/entities/tasks/ui/task-status";
import { ThemeToggle } from "@/entities/theme/ui/theme-toggle";

export function AppHeader() {
  return (
    <Card className="flex h-12.5 items-center gap-2 p-2">
      <TimeFrameSelector />

      <BranchSelector />

      <div className="flex-1" data-testid="breadcrumb-navigation">
        <BreadcrumbNavigation />
      </div>

      <TaskStatus />
      <ThemeToggle />
    </Card>
  );
}
