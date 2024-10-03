import { Link } from "react-router-dom";
import { TimeFrameSelector } from "@/components/time-selector";
import BranchSelector from "@/components/branch-selector";
import InfrahubLogo from "@/images/infrahub-logo.svg";
import { constructPath } from "@/utils/fetch";
import BreadcrumbNavigation from "@/screens/layout/breadcrumb-navigation/breadcrumb-navigation";

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
