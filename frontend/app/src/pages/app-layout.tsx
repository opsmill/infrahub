import { Outlet } from "react-router";

import { AppHeader } from "@/entities/navigation/ui/app-header";
import { AppSidebar } from "@/entities/navigation/ui/sidebar/app-sidebar";
import { InstanceColorBar } from "@/entities/preferences/ui/instance-color-bar";

function AppLayout() {
  return (
    <div className="flex h-screen w-screen flex-col bg-background text-foreground">
      <InstanceColorBar />

      <div className="flex min-h-0 flex-1 flex-col p-0.5">
        <div className="flex min-h-0 w-full flex-1 gap-0.5">
          <AppSidebar />

          <div className="flex h-full grow flex-col gap-0.5 overflow-hidden">
            <AppHeader />

            <Outlet />
          </div>
        </div>
      </div>
    </div>
  );
}

export const Component = AppLayout;
