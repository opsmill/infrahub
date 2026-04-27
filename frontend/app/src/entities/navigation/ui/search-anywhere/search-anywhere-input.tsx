import { Icon } from "@iconify-icon/react";
import { Command, type Command as CommandPrimitive } from "cmdk";
import { useAtom } from "jotai";
import { CaseSensitiveIcon } from "lucide-react";
import type * as React from "react";

import { Button } from "@/shared/components/aria/button";
import { Tooltip } from "@/shared/components/aria/tooltip";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import { searchCaseSensitiveAtom } from "@/entities/navigation/stores/search-case-sensitive.atom";

export function SearchAnywhereInput({
  className,
  ...props
}: React.ComponentProps<typeof CommandPrimitive.Input>) {
  const [caseSensitive, setCaseSensitive] = useAtom(searchCaseSensitiveAtom);

  return (
    <div className="relative">
      <div className="absolute top-2.5 pl-2.5">
        <Icon icon="mdi:magnify" className="text-custom-blue-600 text-xl" />
      </div>

      <Command.Input
        autoFocus
        placeholder="Search for objects, attributes, schemas, documentations ..."
        className={classNames(inputStyle, "pr-10 pl-9", className)}
        data-testid="search-anywhere-input"
        {...props}
      />

      <Tooltip message="Case sensitive">
        <Button
          variant={caseSensitive ? "primary" : "ghost"}
          size="icon"
          onPress={() => setCaseSensitive(!caseSensitive)}
          className={classNames(
            "absolute top-1 right-1 size-8 rounded",
            !caseSensitive && "text-gray-400"
          )}
        >
          <CaseSensitiveIcon className="size-5" />
        </Button>
      </Tooltip>
    </div>
  );
}
