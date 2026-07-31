import { ScrollArea } from "@infrahub/ui";
import { Card } from "@infrahub/ui/card";

import { BranchSelector } from "@/entities/branches/ui/branch-selector";
import { BreadcrumbNavigation } from "@/entities/navigation/ui/breadcrumbs/breadcrumb-navigation";
import { TimeFrameSelector } from "@/entities/navigation/ui/time-selector";
import { TaskStatus } from "@/entities/tasks/ui/task-status";

export function AppHeader() {
  return (
    <Card className="h-12.5 shrink-0 flex-row items-center gap-2 p-2">
      <TimeFrameSelector />

      <BranchSelector />

      <ScrollArea
        scrollX
        scrollBarClassName="hidden"
        className="flex-1"
        data-testid="breadcrumb-navigation"
      >
        <BreadcrumbNavigation />
      </ScrollArea>

      <TaskStatus />
    </Card>
  );
}
