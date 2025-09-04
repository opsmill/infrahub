import { Icon } from "@iconify-icon/react";

import { Button, ButtonProps } from "@/shared/components/buttons/button-primitive";
import { CollapsedButton } from "@/shared/components/layout/menu-navigation/components/collapsed-button";
import Kbd from "@/shared/components/ui/kbd";
import { classNames } from "@/shared/utils/common";

export interface SearchAnywhereTriggerButtonProps extends ButtonProps {
  isCollapsed?: boolean;
}

export function SearchAnywhereTrigger({
  className,
  isCollapsed,
  ...props
}: SearchAnywhereTriggerButtonProps) {
  if (isCollapsed) {
    return (
      <CollapsedButton
        tooltipContent="Search anywhere"
        icon="mdi:search"
        data-testid="search-anywhere-trigger"
        {...props}
      />
    );
  }

  const command = navigator.userAgent.includes("Macintosh") ? "command" : "ctrl";

  return (
    <Button
      variant="ghost"
      className={classNames(
        "px-3 py-2 gap-3 bg-neutral-100 shadow-none text-neutral-800 justify-between",
        className
      )}
      data-testid="search-anywhere-trigger"
      {...props}
    >
      <div className="flex items-center gap-2 overflow-hidden">
        <Icon icon="mdi:magnify" aria-hidden="true" className="text-xl" />
        <span className="text-neutral-700 text-sm group-data-[collapsed=true]/sidebar:hidden transition-all truncate">
          Search
        </span>
      </div>

      <Kbd keys={command} className="group-data-[collapsed=true]/sidebar:hidden transition-all">
        K
      </Kbd>
    </Button>
  );
}
