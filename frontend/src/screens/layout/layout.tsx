import { useState } from "react";
import DeviceList from "../device-list/device-list";
import MobileMenu from "./mobile-menu";
import DesktopMenu from "./desktop-menu";
import Header from "./header";

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <>
      <div className="h-screen flex">
        <MobileMenu sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} />
        <DesktopMenu />

        <div className="flex flex-1 flex-col md:pl-64">
          <Header setSidebarOpen={setSidebarOpen} />
          <DeviceList />
        </div>
      </div>
    </>
  );
}
