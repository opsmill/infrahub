import { Icon } from "@iconify-icon/react";

import { Button, type ButtonProps } from "@/shared/components/buttons/button-primitive";
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
        "justify-between gap-3 bg-neutral-100 px-3 py-2 text-neutral-800 shadow-none",
        className
      )}
      data-testid="search-anywhere-trigger"
      {...props}
    >
      <div className="flex items-center gap-2 overflow-hidden">
        <Icon icon="mdi:magnify" aria-hidden="true" className="text-xl" />
        <span className="truncate text-neutral-700 text-sm transition-all group-data-[collapsed=true]/sidebar:hidden">
          Search
        </span>
      </div>

      <Kbd keys={command} className="transition-all group-data-[collapsed=true]/sidebar:hidden">
        K
      </Kbd>
    </Button>
  );
}
