import { useState } from "react";
import { Outlet } from "react-router-dom";
import DesktopMenu from "./desktop-menu";
import Header from "./header";
import MobileMenu from "./mobile-menu";

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <>
      <div className="h-screen flex">
        <MobileMenu sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} />
        <DesktopMenu />

        <div className="flex flex-1 flex-col md:pl-64 overflow-auto bg-gray-100">
          <Header setSidebarOpen={setSidebarOpen} />

          <div className="flex flex-col flex-1">
            <Outlet />
          </div>
        </div>
      </div>
    </>
  );
}
