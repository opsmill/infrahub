import { Link } from "react-router";

import InfrahubWithTextLogo from "@/assets/Infrahub-SVG-hori.svg";

import { constructPath } from "@/shared/api/rest/fetch";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarProvider,
  SidebarTrigger,
} from "@/shared/components/layout/sidebar";
import { focusVisibleStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import { SearchAnywhere } from "@/entities/navigation/ui/search-anywhere/search-anywhere";
import { SidebarMenu } from "@/entities/navigation/ui/sidebar/sidebar-menu";
import { AccountMenu } from "@/entities/user-profile/ui/account-menu";

export function AppSidebar() {
  return (
    <SidebarProvider>
      <Sidebar data-testid="sidebar" className="divide-y divide-neutral-200">
        <SidebarHeader>
          <AppSidebarHeader />
          <SearchAnywhere />
        </SidebarHeader>

        <SidebarContent>
          <SidebarMenu />
        </SidebarContent>

        <SidebarFooter className="p-1.5">
          <AccountMenu />
        </SidebarFooter>
      </Sidebar>
    </SidebarProvider>
  );
}

function AppSidebarHeader() {
  return (
    <div className="relative h-8 transition-[height] duration-200 ease-linear group-data-[state=collapsed]:h-17.5">
      <Link
        to={constructPath("/")}
        aria-label="Infrahub home"
        className={classNames(
          focusVisibleStyle,
          "absolute bottom-0 left-0 max-w-40 overflow-hidden rounded-md",
          "transition-[left,max-width] duration-200 ease-linear",
          "group-data-[state=collapsed]:left-1.75 group-data-[state=collapsed]:max-w-8"
        )}
      >
        <img src={InfrahubWithTextLogo} alt="Infrahub" className="h-8 max-w-none" />
      </Link>

      <SidebarTrigger className="absolute top-0 right-0 transition-[right] duration-200 ease-linear group-data-[state=collapsed]:right-0.75" />
    </div>
  );
}
