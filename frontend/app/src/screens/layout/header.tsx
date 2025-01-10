import BranchSelector from "@/shared/components/branch-selector";
import { TimeFrameSelector } from "@/shared/components/time-selector";
import InfrahubLogo from "@/assets/infrahub-logo.svg";
import BreadcrumbNavigation from "@/screens/layout/breadcrumb-navigation/breadcrumb-navigation";
import { constructPath } from "@/shared/api/rest/fetch";
import { Link } from "react-router-dom";
import { TaskStatus } from "./tasks-status";

export default function Header() {
  return (
    <header className="px-6 py-3 flex items-center gap-2 border-b bg-white">
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
