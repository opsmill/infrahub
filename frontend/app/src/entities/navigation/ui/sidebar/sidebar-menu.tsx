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

  // Both sections have to be able to give up height, or the one that cannot starves the other:
  // a flex child's automatic minimum size is its content height unless it is a scroll container,
  // so wrapping the internal section in a ScrollArea is what lets it shrink at all. The object
  // section then keeps an explicit floor so it never collapses to an unusable sliver.
  return (
    <>
      <ScrollArea className="min-h-25 flex-1">
        <div className="p-2">
          <SidebarMenuSectionObject items={menu.sections.object} />
        </div>
      </ScrollArea>
      <Separator />
      <ScrollArea>
        <SidebarMenuSectionInternal items={menu.sections.internal} />
      </ScrollArea>
    </>
  );
}
