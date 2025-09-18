import { Icon } from "@iconify-icon/react";
import { Command, type Command as CommandPrimitive } from "cmdk";
import type * as React from "react";

import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

export function SearchAnywhereInput({
  className,
  ...props
}: React.ComponentProps<typeof CommandPrimitive.Input>) {
  return (
    <div className="relative">
      <div className="absolute top-2.5 pl-2.5">
        <Icon icon="mdi:magnify" className="text-custom-blue-600 text-xl" />
      </div>

      <Command.Input
        autoFocus
        placeholder="Search for objects, attributes, schemas, documentations ..."
        className={classNames(inputStyle, "px-9", className)}
        data-testid="search-anywhere-input"
        {...props}
      />
    </div>
  );
}
