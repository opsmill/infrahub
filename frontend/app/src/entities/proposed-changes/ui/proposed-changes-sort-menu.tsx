import { Button, Menu, MenuItem, MenuTrigger, Popover } from "@infrahub/ui";
import { ArrowUpDownIcon, CheckIcon } from "lucide-react";

import { useSort } from "@/entities/nodes/sort/ui/hooks/use-sort";
import {
  PROPOSED_CHANGE_SORT_OPTIONS,
  type ProposedChangeSortOption,
} from "@/entities/proposed-changes/domain/model/proposed-change-sort";
import {
  computeProposedChangeSort,
  isProposedChangeDefaultSort,
  isProposedChangeSortApplied,
} from "@/entities/proposed-changes/domain/rules/proposed-change-sort";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

interface ProposedChangesSortMenuProps {
  schema: ModelSchema;
}

export function ProposedChangesSortMenu({ schema }: ProposedChangesSortMenuProps) {
  const { appliedSort, setCustomSort } = useSort(schema);

  const sort = computeProposedChangeSort(appliedSort);

  const selectOption = (option: ProposedChangeSortOption) => {
    setCustomSort(isProposedChangeDefaultSort(option.sort) ? null : [option.sort]);
  };

  return (
    <MenuTrigger>
      <Button variant="input" size="sm">
        <ArrowUpDownIcon /> Sort
      </Button>

      <Popover placement="bottom start">
        <Menu aria-label="Sort proposed changes" variant="picker">
          {PROPOSED_CHANGE_SORT_OPTIONS.map((option) => (
            <MenuItem
              key={option.id}
              id={option.id}
              textValue={option.label}
              onAction={() => selectOption(option)}
            >
              <span>{option.label}</span>
              {isProposedChangeSortApplied(option.sort, sort) && (
                <>
                  <CheckIcon className="ml-auto" />
                  <span className="sr-only">active</span>
                </>
              )}
            </MenuItem>
          ))}
        </Menu>
      </Popover>
    </MenuTrigger>
  );
}
