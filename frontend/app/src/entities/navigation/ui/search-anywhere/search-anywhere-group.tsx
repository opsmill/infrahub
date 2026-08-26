import { Command } from "cmdk";
import type React from "react";

import { classNames } from "@/shared/utils/common";

export function SearchAnywhereGroup({
  className,
  ...props
}: React.ComponentProps<typeof Command.Group>) {
  return (
    <Command.Group
      className={classNames(
        "rounded-xl border bg-input p-2 shadow-card",
        "[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-subtle [&_[cmdk-group-heading]]:text-xs",
        className
      )}
      {...props}
    />
  );
}
