import ErrorScreen from "@/screens/errors/error-screen";
import { MenuSectionInternal } from "@/screens/layout/menu-navigation/components/menu-section-internal";
import { MenuSectionObject } from "@/screens/layout/menu-navigation/components/menu-section-object";
import { menuQueryOptions } from "@/screens/layout/menu-navigation/get-menu";
import { Divider } from "@/shared/components/ui/divider";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { Spinner } from "@/shared/components/ui/spinner";
import { useQuery } from "@tanstack/react-query";

export interface MenuNavigationProps {
  isCollapsed?: boolean;
}

export default function MenuNavigation({ isCollapsed }: MenuNavigationProps) {
  const { data: menu, isPending, error } = useQuery(menuQueryOptions());

  if (isPending) return <Spinner className="grow mx-auto p-4" />;
  if (error) return <ErrorScreen message="Something went wrong when fetching the menu" />;

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
