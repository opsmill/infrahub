import { useAtomValue } from "jotai/index";
import { useEffect, useMemo, useState } from "react";
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
import { classNames } from "../../utils/common";

export default function Sidebar() {
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

type MenuItem = {
  title: string;
  path: string;
  icon: string;
  children: MenuItem[];
  kind: string;
};

type MenuProps = {
  className?: string;
};
function DesktopMenu({ className = "" }: MenuProps) {
  const branch = useAtomValue(currentBranchAtom);
  const currentSchemaHash = useAtomValue(currentSchemaHashAtom);

  const [isLoading, setIsLoading] = useState(false);
  const [menu, setMenu] = useState<MenuItem[]>([]);
  const [query, setQuery] = useState<string>("");

  const fetchMenu = async () => {
    if (!currentSchemaHash) return;

    try {
      setIsLoading(true);

      const result: MenuItem[] = await fetchUrl(CONFIG.MENU_URL(branch?.name));

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

  function filterDataByString(data: MenuItem[], searchString: string): MenuItem[] {
    const lowercaseSearch = searchString.toLowerCase();

    return data.reduce((acc, item) => {
      const lowercaseTitle = item.title.toLowerCase();
      const filteredChildren = filterDataByString(item.children || [], searchString);

      if (filteredChildren.length > 0 || lowercaseTitle.includes(lowercaseSearch)) {
        acc.push({ ...item, children: filteredChildren });
      }

      return acc;
    }, [] as MenuItem[]);
  }

  const menuFiltered = useMemo(() => filterDataByString(menu, query), [currentSchemaHash, query]);

  return (
    <div className={classNames("flex flex-col", className)}>
      <div className="border-b py-2">
        <SearchInput
          onChange={setQuery}
          containerClassName="z-0"
          className="!shadow-none !ring-0"
          placeholder="Quick navigation"
        />
      </div>

      {isLoading && <LoadingScreen size={32} hideText />}

      {!isLoading && (
        <nav
          className="flex-grow min-h-0 overflow-auto"
          aria-label="Sidebar"
          data-cy="sidebar-menu"
          data-testid="sidebar-menu">
          {(menuFiltered.length > 0 ? menuFiltered : menu).map((item: any, index: number) => (
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
  );
}
