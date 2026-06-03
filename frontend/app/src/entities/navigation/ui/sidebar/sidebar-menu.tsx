import { ScrollArea, Spinner } from "@infrahub/ui";

import { Separator } from "@/shared/components/aria/separator";
import ErrorScreen from "@/shared/components/errors/error-screen";

import { useMenu } from "@/entities/navigation/ui/queries/get-menu.query";
import { SidebarMenuSectionInternal } from "@/entities/navigation/ui/sidebar/sidebar-menu-section-internal";
import { SidebarMenuSectionObject } from "@/entities/navigation/ui/sidebar/sidebar-menu-section-object";

export function SidebarMenu() {
  const { data: menu, isPending, error } = useMenu();

  if (isPending) return <Spinner className="mx-auto grow p-4" />;

  if (error) return <ErrorScreen message="Something went wrong when fetching the menu" />;

  if (!menu?.sections) return <div className="grow" />;

  return (
    <>
      <ScrollArea>
        <div className="p-2">
          <SidebarMenuSectionObject items={menu.sections.object} />
        </div>
      </ScrollArea>
      <Separator />
      <div className="p-2">
        <SidebarMenuSectionInternal items={menu.sections.internal} />
      </div>
    </>
  );
}
