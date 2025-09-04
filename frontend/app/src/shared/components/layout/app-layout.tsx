import { Outlet } from "react-router";

import Sidebar from "@/shared/components/layout/sidebar";

import Header from "./header";

function AppLayout() {
  return (
    <div className="h-screen w-screen bg-stone-100 p-0.5 text-stone-800">
      <div className="flex h-full w-full gap-0.5">
        <Sidebar />

        <div className="flex h-full grow flex-col gap-0.5 overflow-hidden">
          <Header />

          <Outlet />
        </div>
      </div>
    </div>
  );
}

export const Component = AppLayout;
