import { AccountMenu } from "../../components/account-menu";
import { SearchAnywhere } from "../../components/search/search-anywhere";
import { TimeFrameSelector } from "../../components/time-selector";

export default function Header() {
  return (
    <header className="flex items-center justify-between shrink-0 h-16 bg-custom-white border-b gap-4 px-4 py-2">
      <SearchAnywhere className="flex-grow flex justify-center" />

      <div className="w-52 flex justify-end">
        <TimeFrameSelector />
      </div>

      <AccountMenu />
    </header>
  );
}
