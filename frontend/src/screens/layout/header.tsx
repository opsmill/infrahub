import { AccountMenu } from "../../components/account-menu";
import { SearchBar } from "../../components/search/search-bar";

export default function Header() {
  // Search bar after buttons to fix a z-index issue
  return (
    <header className="px-4 relative z-10 flex items-center justify-between gap-4 h-16 bg-custom-white border-b">
      <SearchBar />

      <AccountMenu />
    </header>
  );
}
