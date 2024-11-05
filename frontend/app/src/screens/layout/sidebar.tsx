import { AccountMenu } from "@/components/account-menu";
import { Button } from "@/components/buttons/button-primitive";
import { SearchAnywhere } from "@/components/search/search-anywhere";
import { SIDEBAR_COLLAPSED_KEY } from "@/config/localStorage";
import { useLocalStorage } from "@/hooks/useLocalStorage";
import MenuNavigation from "@/screens/layout/menu-navigation/menu-navigation";
import { classNames } from "@/utils/common";
import { Icon } from "@iconify-icon/react";

export default function Sidebar() {
  const [collapsed, setCollapsed] = useLocalStorage(SIDEBAR_COLLAPSED_KEY);

  const booleanCollapsed = collapsed === "true";

  return (
    <nav
      data-collapsed={booleanCollapsed}
      className={classNames(
        "flex flex-col gap-3 shrink-0",
        "relative -top-px",
        "w-[256px] border rounded-lg py-5 px-4 bg-white",
        "group/sidebar transition-all",
        booleanCollapsed && "w-[72px] px-2 items-center"
      )}
      data-testid="sidebar"
    >
      <Button
        variant="outline"
        size="icon"
        className={classNames(
          "transition-all absolute -right-3.5 top-6",
          booleanCollapsed ? "rotate-180" : "hidden group-hover/sidebar:inline-flex"
        )}
        onClick={() => setCollapsed(JSON.stringify(!booleanCollapsed))}
      >
        <Icon icon="mdi:chevron-left" className="text-xl text-neutral-600" />
      </Button>

      <SearchAnywhere isCollapsed={booleanCollapsed} />

      <MenuNavigation isCollapsed={booleanCollapsed} />

      <AccountMenu />
    </nav>
  );
}
