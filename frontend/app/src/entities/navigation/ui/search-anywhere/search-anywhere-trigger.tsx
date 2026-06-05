import { Icon } from "@iconify-icon/react";
import { Button, type ButtonProps } from "@infrahub/ui";

import Kbd from "@/shared/components/ui/kbd";
import { classNames } from "@/shared/utils/common";

export function SearchAnywhereTrigger({ className, ...props }: ButtonProps) {
  const command = navigator.userAgent.includes("Macintosh") ? "command" : "ctrl";

  return (
    <Button
      variant="outline"
      className={classNames(
        "justify-start px-2 shadow-none group-data-[state=collapsed]:px-2.5",
        className
      )}
      data-testid="search-anywhere-trigger"
      {...props}
    >
      <Icon icon="mdi:magnify" aria-hidden="true" className="text-base" />
      <span className="truncate text-stone-700 group-data-[state=collapsed]:hidden">Search</span>

      <Kbd keys={command} className="ml-auto group-data-[state=collapsed]:hidden">
        K
      </Kbd>
    </Button>
  );
}
