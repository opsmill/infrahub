import { Separator } from "@/shared/components/aria/separator";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { Spinner } from "@/shared/components/ui/spinner";

import { useMenu } from "@/entities/menu/domain/get-menu.query";
import { SidebarMenuSectionInternal } from "@/entities/menu/ui/sidebar-menu-section-internal";
import { SidebarMenuSectionObject } from "@/entities/menu/ui/sidebar-menu-section-object";

export interface MenuNavigationProps {
  isCollapsed?: boolean;
}

export default function SidebarMenu({ isCollapsed }: MenuNavigationProps) {
  const { data: menu, isPending, error } = useMenu();

  if (isPending) return <Spinner className="mx-auto grow p-4" />;

  if (error) return <ErrorScreen message="Something went wrong when fetching the menu" />;

  if (!menu?.sections) return <div className="grow" />;

  return (
    <>
      <ScrollArea>
        <SidebarMenuSectionObject items={menu.sections.object} isCollapsed={isCollapsed} />
      </ScrollArea>
      <Separator />
      <SidebarMenuSectionInternal items={menu.sections.internal} isCollapsed={isCollapsed} />
    </>
  );
}
