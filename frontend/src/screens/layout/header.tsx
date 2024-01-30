import { AccountMenu } from "../../components/account-menu";
import { SearchBar } from "../../components/search/search-bar";

export default function Header() {
  // Search bar after buttons to fix a z-index issue
  return (
    <div className="relative z-10 flex items-center justify-between h-16 bg-custom-white shadow">
      <SearchBar />

      <AccountMenu />
    </div>
  );
}
