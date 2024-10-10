import { AccountMenu } from "@/components/account-menu";
import { SearchAnywhere } from "@/components/search/search-anywhere";
import MenuNavigation from "@/screens/layout/menu-navigation/menu-navigation";

export default function Sidebar() {
  return (
    <nav className="w-[256px] shrink-0 flex flex-col border rounded-lg py-5 px-4 relative -top-px gap-3 bg-white">
      <SearchAnywhere />

      <MenuNavigation className="flex-grow min-h-0 overflow-auto" />

      <AccountMenu />
    </nav>
  );
}
