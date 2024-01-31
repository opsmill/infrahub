import { useAtomValue } from "jotai/index";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "react-toastify";
import BranchSelector from "../../components/branch-selector";
import { SearchInput } from "../../components/search/search-bar";
import { ALERT_TYPES, Alert } from "../../components/utils/alert";
import { CONFIG } from "../../config/config";
import { ReactComponent as InfrahubLogo } from "../../images/Infrahub-SVG-hori.svg";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { currentSchemaHashAtom } from "../../state/atoms/schema.atom";
import { fetchUrl } from "../../utils/fetch";
import LoadingScreen from "../loading-screen/loading-screen";
import DropDownMenuHeader from "./desktop-menu-header";
import { Footer } from "./footer";

export default function DesktopMenu() {
  const branch = useAtomValue(currentBranchAtom);
  const currentSchemaHash = useAtomValue(currentSchemaHashAtom);

  const [isLoading, setIsLoading] = useState(false);
  const [menu, setMenu] = useState([]);

  const fetchMenu = async () => {
    if (!currentSchemaHash) return;

    try {
      setIsLoading(true);

      const result = await fetchUrl(CONFIG.MENU_URL(branch?.name));

      setMenu(result);

      setIsLoading(false);
    } catch (error) {
      console.error("error: ", error);
      toast(<Alert type={ALERT_TYPES.ERROR} message="Error while fetching the menu" />);
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchMenu();
  }, [currentSchemaHash]);

  const onFilterChange = (query: string) => {
    console.log(query);
  };

  return (
    <div className="z-100 hidden w-64 md:flex flex-col border-r">
      <div className="flex flex-grow flex-col overflow-y-auto min-h-0">
        <Link to="/" className="h-16 flex-shrink-0 px-5 flex items-center">
          <InfrahubLogo />
        </Link>

        <div className="border-b flex flex-col items-stretch p-2 gap-2">
          <BranchSelector />
        </div>

        <div className="border-b flex-grow min-h-0 overflow-auto flex flex-col">
          <div className="border-b py-2">
            <SearchInput
              onChange={onFilterChange}
              className="!shadow-none !ring-0"
              placeholder="Filter..."
            />
          </div>

          {isLoading && <LoadingScreen size={32} hideText />}

          {!isLoading && (
            <nav
              className="flex-grow min-h-0 overflow-auto"
              aria-label="Sidebar"
              data-cy="sidebar-menu"
              data-testid="sidebar-menu">
              {menu.map((item: any, index: number) => (
                <DropDownMenuHeader
                  key={index}
                  title={item.title}
                  items={item.children}
                  icon={item.icon}
                />
              ))}
            </nav>
          )}
        </div>
      </div>

      <Footer />
    </div>
  );
}
