import { Button, Menu, MenuItem, MenuTrigger, Popover } from "@infrahub/ui";
import { ArrowUpDownIcon, CheckIcon } from "lucide-react";
import type { Selection } from "react-aria-components";

import { parseSortToken, serializeSortToken } from "@/entities/nodes/sort/domain/rules/sort-token";
import { useSort } from "@/entities/nodes/sort/ui/hooks/use-sort";
import type { ProposedChangeSortToken } from "@/entities/proposed-changes/domain/model/proposed-change-sort";
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
          selectionMode="single"
          disallowEmptySelection
          selectedKeys={selectedKeys}
          onSelectionChange={selectSort}
        >
          {/* Wording follows the sort menu on GitHub pull requests, which users arrive here already knowing. */}
          <SortMenuItem id="node_metadata__created_at__desc">Newest</SortMenuItem>
          <SortMenuItem id="node_metadata__created_at__asc">Oldest</SortMenuItem>
          <SortMenuItem id="node_metadata__updated_at__desc">Recently updated</SortMenuItem>
          <SortMenuItem id="node_metadata__updated_at__asc">Least recently updated</SortMenuItem>
        </Menu>
      </Popover>
    </MenuTrigger>
  );
}

interface SortMenuItemProps {
  /** Doubles as the menu's selection key, so it has to be the token the URL carries. */
  id: ProposedChangeSortToken;
  children: string;
}

function SortMenuItem({ id, children }: SortMenuItemProps) {
  return (
    <MenuItem id={id} textValue={children}>
      {({ isSelected }) => (
        <>
          <span>{children}</span>
          {isSelected && <CheckIcon className="ml-auto" />}
        </>
      )}
    </MenuItem>
  );
}
