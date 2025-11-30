import { Separator } from "@/shared/components/aria/separator";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { Spinner } from "@/shared/components/ui/spinner";

import { useMenu } from "@/entities/menu/domain/get-menu.query";
import { MenuSectionInternal } from "@/entities/menu/ui/menu-section-internal";
import { MenuSectionObject } from "@/entities/menu/ui/menu-section-object";

export interface MenuNavigationProps {
  isCollapsed?: boolean;
}

export default function MenuNavigation({ isCollapsed }: MenuNavigationProps) {
  const { data: menu, isPending, error } = useMenu();

  if (isPending) return <Spinner className="mx-auto grow p-4" />;

  if (error) return <ErrorScreen message="Something went wrong when fetching the menu" />;

  if (!menu?.sections) return <div className="grow" />;

  return (
    <>
      <ScrollArea>
        <MenuSectionObject items={menu.sections.object} isCollapsed={isCollapsed} />
      </ScrollArea>
      <Separator />
      <MenuSectionInternal items={menu.sections.internal} isCollapsed={isCollapsed} />
    </>
  );
}
