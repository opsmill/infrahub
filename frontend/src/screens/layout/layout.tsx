import { useState } from "react";
import MobileMenu from "./mobile-menu";
import DesktopMenu from "./desktop-menu";
import Header from "./header";
import OpsObjects from "../ops-objects/ops-objects";

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <>
      <div className="h-screen flex">
        <MobileMenu sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} />
        <DesktopMenu />

        <div className="flex flex-1 flex-col md:pl-64">
          <Header setSidebarOpen={setSidebarOpen} />
          <OpsObjects />
          {/* <DeviceList /> */}
        </div>
      </div>
    </>
  );
}
