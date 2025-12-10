import { Outlet } from "react-router";

import { AppHeader } from "@/entities/navigation/ui/app-header";
import { AppSidebar } from "@/entities/navigation/ui/sidebar/app-sidebar";

function AppLayout() {
  return (
    <div className="h-screen w-screen bg-stone-100 p-0.5 text-stone-800">
      <div className="flex h-full w-full gap-0.5">
        <AppSidebar />

        <div className="flex h-full grow flex-col gap-0.5 overflow-hidden">
          <AppHeader />

          <Outlet />
        </div>
      </div>
    </div>
  );
}

export const Component = AppLayout;
