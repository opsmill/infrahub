import { Button, Menu, MenuItem, MenuTrigger, Popover } from "@infrahub/ui";
import { ArrowUpDownIcon, CheckIcon } from "lucide-react";
import type { Selection } from "react-aria-components";

import { parseSortToken, serializeSortToken } from "@/entities/nodes/sort/domain/rules/sort-token";
import { useSort } from "@/entities/nodes/sort/ui/hooks/use-sort";
import { PROPOSED_CHANGE_SORT_OPTIONS } from "@/entities/proposed-changes/domain/model/proposed-change-sort";
import {
  computeProposedChangeSort,
  isProposedChangeDefaultSort,
} from "@/entities/proposed-changes/domain/rules/proposed-change-sort";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

interface ProposedChangesSortMenuProps {
  schema: ModelSchema;
}

export function ProposedChangesSortMenu({ schema }: ProposedChangesSortMenuProps) {
  const { appliedSort, setCustomSort } = useSort(schema);

  const sort = computeProposedChangeSort(appliedSort);

  // Sort tokens are the menu's selection keys, so the applied order names its own item. Only a
  // single-key order can: a multi-key one from the URL is honoured with nothing selected.
  const selectedKeys = sort.length === 1 && sort[0] ? [serializeSortToken(sort[0])] : [];

  const selectSort = (keys: Selection) => {
    const [token] = keys === "all" ? [] : [...keys];
    if (!token) return;

    const selected = parseSortToken(String(token));
    setCustomSort(isProposedChangeDefaultSort(selected) ? null : [selected]);
  };

  return (
    <MenuTrigger>
      <Button variant="input" size="sm">
        <ArrowUpDownIcon /> Sort
      </Button>

      <Popover placement="bottom start">
        <Menu
          aria-label="Sort proposed changes"
          variant="picker"
          items={PROPOSED_CHANGE_SORT_OPTIONS}
          selectionMode="single"
          disallowEmptySelection
          selectedKeys={selectedKeys}
          onSelectionChange={selectSort}
        >
          {(option) => (
            <MenuItem id={serializeSortToken(option.sort)} textValue={option.label}>
              {({ isSelected }) => (
                <>
                  <span>{option.label}</span>
                  {isSelected && <CheckIcon className="ml-auto" />}
                </>
              )}
            </MenuItem>
          )}
        </Menu>
      </Popover>
    </MenuTrigger>
  );
}
