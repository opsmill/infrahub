import { AccountMenu } from "@/components/account-menu";
import { Button } from "@/components/buttons/button-primitive";
import { SearchAnywhere } from "@/components/search/search-anywhere";
import MenuNavigation from "@/screens/layout/menu-navigation/menu-navigation";
import { classNames } from "@/utils/common";
import { Icon } from "@iconify-icon/react";
import { useState } from "react";

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <nav
      data-collapsed={collapsed}
      className={classNames(
        "flex flex-col gap-3 shrink-0",
        "relative -top-px",
        "w-[256px] border rounded-lg py-5 px-4 bg-white",
        "group/sidebar transition-all",
        collapsed && "w-[72px] px-2 items-center"
      )}
    >
      <Button
        variant="outline"
        size="icon"
        className={classNames(
          "transition-all absolute -right-3.5 top-6",
          collapsed ? "rotate-180" : "hidden group-hover/sidebar:inline-flex"
        )}
        onClick={() => setCollapsed(!collapsed)}
      >
        <Icon icon="mdi:chevron-left" className="text-xl text-neutral-600" />
      </Button>

      <SearchAnywhere isCollapsed={collapsed} />

      <MenuNavigation isCollapsed={collapsed} />

      <AccountMenu />
    </nav>
  );
}
