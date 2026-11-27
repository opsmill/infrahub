import { Command, type Command as CommandPrimitive } from "cmdk";
import { useAtom } from "jotai";
import type * as React from "react";

import { Icon } from "@/shared/components/display/icon";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import { searchCaseSensitiveAtom } from "@/entities/navigation/stores/search-case-sensitive.atom";
import { SearchCaseSensitiveToggle } from "@/entities/navigation/ui/search-case-sensitive-toggle";

export function SearchAnywhereInput({
  className,
  ...props
}: React.ComponentProps<typeof CommandPrimitive.Input>) {
  const [caseSensitive, setCaseSensitive] = useAtom(searchCaseSensitiveAtom);

  return (
    <div className="relative">
      <div className="absolute top-2.5 pl-2.5">
        <Icon icon="mdi:magnify" className="text-accent text-xl" />
      </div>

      <Command.Input
        autoFocus
        placeholder="Search for objects, attributes, schemas, documentations ..."
        className={classNames(inputStyle, "pr-10 pl-9", className)}
        data-testid="search-anywhere-input"
        {...props}
      />

      <SearchCaseSensitiveToggle
        isSelected={caseSensitive}
        onChange={setCaseSensitive}
        className="absolute top-1 right-1"
      />
    </div>
  );
}
