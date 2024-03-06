import { AccountMenu } from "../../components/account-menu";
import { SearchModal } from "../../components/search/search-modal";
import { TimeFrameSelector } from "../../components/TimeFrameSelector";

export default function Header() {
  return (
    <header className="flex items-center justify-between shrink-0 h-16 bg-custom-white border-b gap-4 px-4 py-2">
      <SearchModal className="flex-grow flex justify-center" />

      <TimeFrameSelector />

      <AccountMenu />
    </header>
  );
}
