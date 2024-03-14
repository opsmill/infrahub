import { useAtomValue } from "jotai/index";
import { useEffect, useMemo, useState } from "react";
import { toast } from "react-toastify";
import { SearchInput } from "../../../components/search/search-bar";
import { ALERT_TYPES, Alert } from "../../../components/utils/alert";
import { CONFIG } from "../../../config/config";
import { currentBranchAtom } from "../../../state/atoms/branches.atom";
import { currentSchemaHashAtom } from "../../../state/atoms/schema.atom";
import { fetchUrl } from "../../../utils/fetch";
import LoadingScreen from "../../loading-screen/loading-screen";
import DropDownMenuHeader from "./desktop-menu-header";
import { classNames } from "../../../utils/common";

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
export function DesktopMenu({ className = "" }: MenuProps) {
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
          containerClassName="!z-0"
          className="!shadow-none !ring-0"
          placeholder="Search menu"
          testId="search-menu"
        />
      </div>

      {isLoading && <LoadingScreen size={32} hideText />}

      {!isLoading && (
        <nav
          className="flex-grow min-h-0 overflow-y-auto overflow-x-hidden"
          aria-label="Sidebar"
          data-cy="sidebar-menu"
          data-testid="sidebar-menu">
          {(query !== "" ? menuFiltered : menu).map((item: any, index: number) => (
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
