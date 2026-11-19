import { ScrollArea } from "@infrahub/ui";
import { Command } from "cmdk";
import type React from "react";

import { classNames } from "@/shared/utils/common";

interface SearchAnywhereGroupProps extends React.ComponentProps<typeof Command.Group> {
  viewportRef?: React.Ref<HTMLDivElement>;
}

export function SearchAnywhereGroup({
  heading,
  className,
  viewportRef,
  ...props
}: SearchAnywhereGroupProps) {
  return (
    <ScrollArea
      ref={viewportRef}
      className={classNames(
        "mt-2 flex shrink-0 flex-col rounded-xl border bg-input shadow-card",
        className
      )}
    >
      <Command.Group
        heading={
          heading && (
            <span className="block px-2 py-1.5 font-medium text-subtle text-xs">{heading}</span>
          )
        }
        className="p-2"
        {...props}
      />
    </ScrollArea>
  );
}
