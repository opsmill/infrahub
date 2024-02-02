import { Link } from "react-router-dom";
import BranchSelector from "../../../components/branch-selector";
import { Footer } from "../footer";
import { DesktopMenu } from "./desktop-menu";
import { ReactComponent as InfrahubLogo } from "../../../images/Infrahub-SVG-hori.svg";

export function Sidebar() {
  return (
    <div className="z-100 hidden w-64 md:flex flex-col border-r">
      <div className="flex flex-grow flex-col overflow-y-auto min-h-0">
        <Link to="/" className="h-16 flex-shrink-0 px-5 flex items-center">
          <InfrahubLogo />
        </Link>

        <div className="border-b flex flex-col items-stretch p-2 gap-2">
          <BranchSelector />
        </div>

        <DesktopMenu className="border-b flex-grow min-h-0 overflow-auto " />
      </div>

      <Footer />
    </div>
  );
}
