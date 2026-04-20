import { Card } from "@/shared/components/ui/card";
import { ScrollArea } from "@/shared/components/ui/scroll-area";

import BranchSelector from "@/entities/branches/ui/branch-selector";
import { BreadcrumbNavigation } from "@/entities/navigation/ui/breadcrumbs/breadcrumb-navigation";
import { TimeFrameSelector } from "@/entities/navigation/ui/time-selector";
import { TaskStatus } from "@/entities/tasks/ui/task-status";

export function AppHeader() {
  return (
    <Card className="flex h-12.5 shrink-0 items-center gap-2 overflow-hidden p-2">
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
