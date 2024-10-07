import { AccountMenu } from "@/components/account-menu";
import { SearchAnywhere } from "@/components/search/search-anywhere";
import { DesktopMenu } from "@/screens/layout/sidebar/desktop-menu";

export default function Sidebar() {
  return (
    <nav className="w-[256px] shrink-0 flex flex-col border rounded-lg py-5 px-4 relative -top-px gap-3 bg-white">
      <SearchAnywhere />

      <DesktopMenu className="flex-grow min-h-0 overflow-auto " />

      <AccountMenu />
    </nav>
  );
}
