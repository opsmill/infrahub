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

          <main className="flex-1 overflow-auto">
            <div className="pt-6">
              {/* <div className="mx-auto max-w-7xl px-4 sm:px-6 md:px-8"> */}
              <div className="mx-auto px-4 sm:px-0 md:px-0">
                <DeviceList />
              </div>
            </div>
          </main>
        </div>
      </div>
    </>
  );
}
