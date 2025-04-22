import ErrorScreen from "@/shared/components/errors/error-screen";
import { MenuSectionInternal } from "@/shared/components/layout/menu-navigation/components/menu-section-internal";
import { MenuSectionObject } from "@/shared/components/layout/menu-navigation/components/menu-section-object";
import { useMenu } from "@/shared/components/menu/domain/get-menu.query";
import { Divider } from "@/shared/components/ui/divider";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { Spinner } from "@/shared/components/ui/spinner";

export interface MenuNavigationProps {
  isCollapsed?: boolean;
}

export default function MenuNavigation({ isCollapsed }: MenuNavigationProps) {
  const { data: menu, isPending, error } = useMenu();

  if (isPending) return <Spinner className="grow mx-auto p-4" />;
  if (error) return <ErrorScreen message="Something went wrong when fetching the menu" />;

  if (!menu?.sections) return <div className="grow" />;

  return (
    <>
      <ScrollArea>
        <MenuSectionObject items={menu.sections.object} isCollapsed={isCollapsed} />
      </ScrollArea>
      <Divider />
      <MenuSectionInternal items={menu.sections.internal} isCollapsed={isCollapsed} />
    </>
  );
}
