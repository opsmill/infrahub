import { Outlet } from "react-router";

import Sidebar from "@/shared/components/layout/sidebar";

import Header from "./header";

function AppLayout() {
  return (
    <div className="h-screen w-screen text-stone-800 p-0.5 bg-stone-100">
      <div className="h-full w-full flex gap-0.5">
        <Sidebar />

        <div className="flex flex-col gap-0.5 h-full grow overflow-hidden">
          <Header />

          <Outlet />
        </div>
      </div>
    </div>
  );
}

export const Component = AppLayout;
