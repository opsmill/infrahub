import { Button, Menu, MenuItem, MenuTrigger, Popover } from "@infrahub/ui";
import { ArrowUpDownIcon, CheckIcon } from "lucide-react";
import type { Selection } from "react-aria-components";

import type { SortToken } from "@/entities/nodes/sort/domain/model/sort";
import { parseSortToken, serializeSortToken } from "@/entities/nodes/sort/domain/rules/sort-token";
import { useSort } from "@/entities/nodes/sort/ui/hooks/use-sort";
import { PROPOSED_CHANGE_DEFAULT_SORT } from "@/entities/proposed-changes/domain/model/proposed-change-sort";
import { computeProposedChangeSort } from "@/entities/proposed-changes/domain/rules/compute-proposed-change-sort";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

interface ProposedChangesSortMenuProps {
  schema: ModelSchema;
}

export function ProposedChangesSortMenu({ schema }: ProposedChangesSortMenuProps) {
  const { appliedSort, setCustomSort } = useSort(schema);

  const sort = computeProposedChangeSort(appliedSort);
  const selectedKeys = sort.length === 1 && sort[0] ? [serializeSortToken(sort[0])] : [];

  const selectSort = (keys: Selection) => {
    const [sortToken] = keys === "all" ? [] : [...keys];
    if (!sortToken) return;

    const defaultSortToken = serializeSortToken(PROPOSED_CHANGE_DEFAULT_SORT);
    setCustomSort(sortToken === defaultSortToken ? null : [parseSortToken(String(sortToken))]);
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
  id: SortToken;
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
