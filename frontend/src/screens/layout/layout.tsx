import { Outlet } from "react-router-dom";
import DesktopMenu from "./desktop-menu";
import Header from "./header";

export default function Layout() {
  return (
    <>
      <div className="h-screen flex overflow-x-hidden">
        <DesktopMenu />

        <div className="flex flex-1 flex-col bg-gray-100 overflow-y-scroll overflow-x-hidden">
          <Header />

          <div className="flex flex-col flex-1">
            <Outlet />
          </div>
        </div>
      </div>
    </>
  );
}
