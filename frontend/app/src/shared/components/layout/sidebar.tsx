import { PanelLeftCloseIcon, PanelLeftOpenIcon } from "lucide-react";
import { Link } from "react-router";

import InfrahubWithTextLogo from "@/assets/Infrahub-SVG-hori.svg";
import InfrahubLogo from "@/assets/infrahub-logo.svg";

import { constructPath } from "@/shared/api/rest/fetch";
import { AccountMenu } from "@/shared/components/account-menu";
import { Separator } from "@/shared/components/aria/separator";
import { Button } from "@/shared/components/buttons/button-primitive";
import { Card } from "@/shared/components/ui/card";
import { focusVisibleStyle } from "@/shared/components/ui/style";
import { useLocalStorage } from "@/shared/hooks/useLocalStorage";
import { classNames } from "@/shared/utils/common";

import { SIDEBAR_COLLAPSED_KEY } from "@/entities/menu/constants";
import SidebarMenu from "@/entities/menu/ui/sidebar-menu";
import { SearchAnywhere } from "@/entities/search-anywhere/ui/search-anywhere";

export default function Sidebar() {
  const [collapsed, setCollapsed] = useLocalStorage(SIDEBAR_COLLAPSED_KEY);

  const booleanCollapsed = collapsed === "true";

  return (
    <Card
      data-collapsed={booleanCollapsed}
      className={classNames(
        "relative flex w-[256px] shrink-0 flex-col gap-3",
        "group/sidebar transition-all",
        booleanCollapsed && "w-auto items-center px-2"
      )}
      data-testid="sidebar"
    >
      <div className="flex items-center justify-between">
        <Link to={constructPath("/")} className={classNames(focusVisibleStyle, "rounded-md")}>
          <img
            src={booleanCollapsed ? InfrahubLogo : InfrahubWithTextLogo}
            alt="Infrahub logo"
            className={"m-0.5 h-8 px-1"}
          />
        </Link>

        {booleanCollapsed ? (
          <Button
            variant="outline"
            size="icon"
            className="-right-3.5 absolute top-11 hidden transition-all group-hover/sidebar:inline-flex"
            onClick={() => setCollapsed(JSON.stringify(!booleanCollapsed))}
          >
            <PanelLeftOpenIcon className="size-4 text-neutral-600" />
          </Button>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            className="p-1 text-gray-400 hover:text-neutral-600"
            onClick={() => setCollapsed(JSON.stringify(!booleanCollapsed))}
          >
            <PanelLeftCloseIcon className="size-5" />
          </Button>
        )}
      </div>

      <SearchAnywhere isCollapsed={booleanCollapsed} />

      <Separator />

      <SidebarMenu isCollapsed={booleanCollapsed} />

      <AccountMenu />
    </Card>
  );
}
