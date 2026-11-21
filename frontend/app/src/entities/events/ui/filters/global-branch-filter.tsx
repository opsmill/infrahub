import { useAtomValue } from "jotai";
import { useEffect } from "react";
import type { TagProps } from "react-aria-components";

import { branchesState } from "@/entities/branches/stores";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { EventFilterTag } from "@/entities/events/ui/filters/event-filter-tag";
import { GlobalFilterForm } from "@/entities/events/ui/filters/global-filter-form";
import { useFilters } from "@/entities/nodes/filters/ui/hooks/use-filters";

interface FilterTagProps extends TagProps {}

const branchFilterName = "branches__value" as const;

export function GlobalBranchFilter({ ...props }: FilterTagProps) {
  const branches = useAtomValue(branchesState);

  const [filters, setFilters] = useFilters();
  const { currentBranch } = useCurrentBranch();

  const currentFilter = filters.find((filter) => filter.name === branchFilterName);

  const handleRemoveFilter = () => {
    setFilters([
      ...filters.filter((filter) => filter.name !== branchFilterName),
      { name: branchFilterName, value: null },
    ]);
  };

  useEffect(() => {
    if (currentBranch.is_default || currentFilter) return;

    // Set the current branch if it's not the default one and if it has not been removed from the filters
    setFilters([...filters, { name: branchFilterName, value: currentBranch.name }]);
  }, []);

  return (
    <EventFilterTag
      label="Branch"
      tagLabel="branches"
      tabLabel="branch"
      currentFilter={currentFilter}
      renderValue={() => currentFilter?.value}
      onRemove={handleRemoveFilter}
      renderForm={(close) => (
        <GlobalFilterForm
          name="branches"
          fieldSchema={{
            kind: "Dropdown",
            choices: branches.map((branch) => {
              return {
                label: branch.name,
                name: branch.name,
              };
            }),
          }}
          onSuccess={close}
        />
      )}
      {...props}
    />
  );
}
