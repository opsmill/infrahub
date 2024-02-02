import { Outlet } from "react-router-dom";
import Header from "./header";
import { Sidebar } from "./sidebar";

export default function Layout() {
  return (
    <div className="h-screen flex overflow-x-hidden">
      <Sidebar />

      <div className="flex flex-1 flex-col bg-gray-100 overflow-y-scroll overflow-x-hidden">
        <Header />

        <main className="flex flex-col flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
