import InfrahubLogo from "@/assets/infrahub-logo.svg";
import { TaskStatus } from "@/entities/tasks/ui/task-status";
import { constructPath } from "@/shared/api/rest/fetch";
import BranchSelector from "@/shared/components/branch-selector";
import BreadcrumbNavigation from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-navigation";
import { TimeFrameSelector } from "@/shared/components/time-selector";
import { Link } from "react-router";

export default function Header() {
  return (
    <header className="px-6 py-3 flex items-center gap-2 border bg-white rounded-lg">
      <Link to={constructPath("/")} className="h-8 w-8">
        <img src={InfrahubLogo} alt="Infrahub logo" />
      </Link>

      <TimeFrameSelector />

      <BranchSelector />

      <div className="flex-1">
        <BreadcrumbNavigation />
      </div>

      <TaskStatus />
    </header>
  );
}
