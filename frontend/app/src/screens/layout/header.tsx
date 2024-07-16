import { AccountMenu } from "@/components/account-menu";
import { SearchAnywhere } from "@/components/search/search-anywhere";
import { TimeFrameSelector } from "@/components/time-selector";
import { Icon } from "@iconify-icon/react";
import { Button } from "@/components/buttons/button-primitive";

type HeaderProps = {
  isSidebarVisible: boolean;
  onMenuToggle: () => void;
};

export default function Header({ isSidebarVisible, onMenuToggle }: HeaderProps) {
  return (
    <header className="flex items-center justify-between shrink-0 h-16 bg-custom-white border-b gap-4 px-4 py-2">
      <Button
        size="icon"
        variant="ghost"
        onClick={onMenuToggle}
        data-testid="sidebar-toggle-button">
        <Icon
          icon={isSidebarVisible ? "mdi:menu-open" : "mdi:menu-close"}
          className="text-xl text-custom-blue-800"
        />
      </Button>

      <SearchAnywhere className="flex-grow flex justify-center" />

      <div className="w-[222px] flex justify-end">
        <TimeFrameSelector />
      </div>

      <AccountMenu />
    </header>
  );
}
