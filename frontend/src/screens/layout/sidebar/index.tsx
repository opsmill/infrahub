import { Link } from "react-router-dom";
import { ReactComponent as InfrahubLogo } from "../../../images/Infrahub-SVG-hori.svg";
import BranchSelector from "../@/components/branch-selector";
import { Footer } from "../footer";
import { DesktopMenu } from "./desktop-menu";

export function Sidebar() {
  return (
    <div className="z-100 w-64 flex flex-col border-r">
      <div className="flex flex-grow flex-col overflow-y-auto min-h-0">
        <Link to="/" className="h-16 flex-shrink-0 px-5 flex items-center">
          <InfrahubLogo />
        </Link>

        <div className="h-16 border-b flex items-center p-2 gap-2">
          <BranchSelector />
        </div>

        <DesktopMenu className="border-b flex-grow min-h-0 overflow-auto " />
      </div>

      <Footer />
    </div>
  );
}
