import BranchSelector from "@/components/branch-selector";
import { TimeFrameSelector } from "@/components/time-selector";
import InfrahubLogo from "@/images/infrahub-logo.svg";
import BreadcrumbNavigation from "@/screens/layout/breadcrumb-navigation/breadcrumb-navigation";
import { constructPath } from "@/utils/fetch";
import { Link } from "react-router-dom";

export default function Header() {
  return (
    <header className="px-6 py-3 flex items-center gap-2 border-b bg-white">
      <Link to={constructPath("/")} className="h-8 w-8">
        <img src={InfrahubLogo} alt="Infrahub logo" />
      </Link>

      <TimeFrameSelector />

      <BranchSelector />

      <BreadcrumbNavigation />
    </header>
  );
}
