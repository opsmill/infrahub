import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { Divider } from "@/components/ui/divider";
import { ScrollArea } from "@/components/ui/scroll-area";
import { CONFIG } from "@/config/config";
import { MenuSectionInternal } from "@/screens/layout/menu-navigation/components/menu-section-internal";
import { MenuSectionObject } from "@/screens/layout/menu-navigation/components/menu-section-object";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { currentSchemaHashAtom, menuAtom } from "@/state/atoms/schema.atom";
import { fetchUrl } from "@/utils/fetch";
import { useAtom, useAtomValue } from "jotai";
import { useEffect, useState } from "react";
import { toast } from "react-toastify";

export interface MenuNavigationProps {
  isCollapsed?: boolean;
}

export default function MenuNavigation({ isCollapsed }: MenuNavigationProps) {
  const currentBranch = useAtomValue(currentBranchAtom);
  const currentSchemaHash = useAtomValue(currentSchemaHashAtom);
  const [menu, setMenu] = useAtom(menuAtom);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!currentSchemaHash) return;

    try {
      setIsLoading(true);
      fetchUrl(CONFIG.MENU_URL(currentBranch?.name)).then((menu) => setMenu(menu));
    } catch (error) {
      console.error("error: ", error);
      toast(<Alert type={ALERT_TYPES.ERROR} message="Error while fetching the menu" />);
    } finally {
      setIsLoading(false);
    }
  }, [currentSchemaHash]);

  if (isLoading) return <div>Loading...</div>;
  if (!menu?.sections) return <div className="flex-grow" />;

  return (
    <>
      <ScrollArea>
        <MenuSectionObject items={menu.sections.object} isCollapsed={isCollapsed} />
      </ScrollArea>
      <Divider className="p-0" />
      <MenuSectionInternal items={menu.sections.internal} isCollapsed={isCollapsed} />
    </>
  );
}
