import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { Command, Command as CommandPrimitive } from "cmdk";
import * as React from "react";

export function SearchAnywhereInput({
  className,
  ...props
}: React.ComponentProps<typeof CommandPrimitive.Input>) {
  return (
    <div className="relative">
      <div className="absolute top-2.5 pl-2.5">
        <Icon icon="mdi:magnify" className="text-xl text-custom-blue-600" />
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
