import { Button, Tooltip } from "@infrahub/ui";
import { Command, type Command as CommandPrimitive } from "cmdk";
import { useAtom } from "jotai";
import { CaseSensitiveIcon, WholeWordIcon } from "lucide-react";
import type * as React from "react";

import { Icon } from "@/shared/components/display/icon";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import { searchCaseSensitiveAtom } from "@/entities/navigation/stores/search-case-sensitive.atom";
import { searchExactMatchAtom } from "@/entities/navigation/stores/search-exact-match.atom";

export function SearchAnywhereInput({
  className,
  ...props
}: React.ComponentProps<typeof CommandPrimitive.Input>) {
  const [caseSensitive, setCaseSensitive] = useAtom(searchCaseSensitiveAtom);
  const [exactMatch, setExactMatch] = useAtom(searchExactMatchAtom);

  return (
    <div className="relative">
      <div className="absolute top-2.5 pl-2.5">
        <Icon icon="mdi:magnify" className="text-accent text-xl" />
      </div>

      <Command.Input
        autoFocus
        placeholder="Search for objects, attributes, schemas, documentations ..."
        className={classNames(inputStyle, "pr-18 pl-9", className)}
        data-testid="search-anywhere-input"
        {...props}
      />

      <Tooltip message="Exact match">
        <Button
          variant={exactMatch ? "primary" : "ghost"}
          size="xs"
          shape="circle"
          aria-label="Exact match"
          aria-pressed={exactMatch}
          onPress={() => setExactMatch(!exactMatch)}
          className={classNames(
            "absolute top-1 right-9 size-8 rounded",
            !exactMatch && "text-subtle-muted"
          )}
        >
          <WholeWordIcon className="size-5" />
        </Button>
      </Tooltip>

      <Tooltip message="Case sensitive">
        <Button
          variant={caseSensitive ? "primary" : "ghost"}
          size="xs"
          shape="circle"
          aria-label="Case sensitive"
          aria-pressed={caseSensitive}
          onPress={() => setCaseSensitive(!caseSensitive)}
          className={classNames(
            "absolute top-1 right-1 size-8 rounded",
            !caseSensitive && "text-subtle-muted"
          )}
        >
          <CaseSensitiveIcon className="size-5" />
        </Button>
      </Tooltip>
    </div>
  );
}
