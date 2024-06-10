import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { SearchInput } from "@/components/ui/search-input";
import { CONFIG } from "@/config/config";
import { currentBranchAtom } from "@/state/state/atoms/branches.atom";
import { currentSchemaHashAtom, menuAtom } from "@/state/state/atoms/schema.atom";
import { classNames } from "@/utils/common";
import { fetchUrl } from "@/utils/fetch";
import { useAtom, useAtomValue } from "jotai/index";
import { useEffect, useMemo, useState } from "react";
import { toast } from "react-toastify";
import LoadingScreen from "../../loading-screen/loading-screen";
import DropDownMenuHeader from "./desktop-menu-header";

export type MenuItem = {
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
  const [menu, setMenu] = useAtom(menuAtom);

  const [isLoading, setIsLoading] = useState(false);
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
        acc.push({
          ...item,
          children: filteredChildren.length > 0 ? filteredChildren : item.children,
        });
      }

      return acc;
    }, [] as MenuItem[]);
  }

  const menuFiltered = useMemo(
    () => filterDataByString(menu, query),
    [currentSchemaHash, query, menu.length]
  );

  return (
    <div className={classNames("flex flex-col", className)}>
      <SearchInput
        onChange={(e) => setQuery(e.target.value)}
        className="shadow-none border-0 rounded-none border-b border-gray-200 focus-visible:ring-0 py-4"
        placeholder="Search menu"
        data-testid="search-menu"
      />

      {isLoading && <LoadingScreen size={32} hideText />}

      {!isLoading && (
        <nav
          className="flex-grow min-h-0 overflow-y-auto overflow-x-hidden"
          aria-label="Sidebar"
          data-cy="sidebar-menu"
          data-testid="sidebar-menu">
          {(query !== "" ? menuFiltered : menu).map((item, index: number) => (
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
