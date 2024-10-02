import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { CONFIG } from "@/config/config";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { currentSchemaHashAtom, menuAtom } from "@/state/atoms/schema.atom";
import { classNames } from "@/utils/common";
import { fetchUrl } from "@/utils/fetch";
import { useAtom, useAtomValue } from "jotai/index";
import { useEffect, useState } from "react";
import { toast } from "react-toastify";
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

  return (
    <div className={classNames("flex flex-col", className)}>
      {isLoading && <LoadingScreen size={32} hideText />}

      {!isLoading && (
        <nav
          className="flex-grow min-h-0 overflow-y-auto overflow-x-hidden"
          aria-label="Sidebar"
          data-cy="sidebar-menu"
          data-testid="sidebar-menu">
          {menu.map((item, index: number) => (
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
