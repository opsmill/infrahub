import { TaskStatus } from "@/entities/tasks/ui/task-status";
import BranchSelector from "@/shared/components/branch-selector";
import BreadcrumbNavigation from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-navigation";
import { TimeFrameSelector } from "@/shared/components/time-selector";

export default function Header() {
  return (
    <header className="p-3 flex items-center gap-2 border bg-white rounded-lg">
      <TimeFrameSelector />

      <BranchSelector />

      <div className="flex-1">
        <BreadcrumbNavigation />
      </div>

      <TaskStatus />
    </header>
  );
}
