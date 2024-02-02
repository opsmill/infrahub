import { AccountMenu } from "../../components/account-menu";
import { SearchBar } from "../../components/search/search-bar";
import { TimeFrameSelector } from "../../components/TimeFrameSelector";

export default function Header() {
  return (
    <header className="relative z-10 flex items-center justify-between h-16 bg-custom-white border-b gap-4 px-4 py-2">
      <SearchBar />

      <TimeFrameSelector />

      <AccountMenu />
    </header>
  );
}
