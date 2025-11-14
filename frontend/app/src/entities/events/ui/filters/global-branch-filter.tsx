import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { useEffect, useState } from "react";
import type { TagProps } from "react-aria-components";

import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import useFilters from "@/shared/hooks/useFilters";

import { branchesState } from "@/entities/branches/stores";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { GlobalFilterForm } from "@/entities/events/ui/filters/global-filter-form";
import { FilterTag } from "@/entities/events/ui/filters/global-filter-tag";

interface FilterTagProps extends TagProps {}

const branchFilterName = "branches__value" as const;

export function GlobalBranchFilter({ ...props }: FilterTagProps) {
  const branches = useAtomValue(branchesState);

  const [filters, setFilters] = useFilters();
  const { currentBranch } = useCurrentBranch();
  const [showFilters, setShowFilters] = useState(false);

  const currentFilter = filters.find((filter) => filter.name === branchFilterName);

  const handleRemoveFilter = () => {
    setFilters([
      ...filters.filter((filter) => filter.name !== branchFilterName),
      { name: branchFilterName, value: null },
    ]);
  };

  useEffect(() => {
    if (currentBranch.name === "main" || currentFilter) return;

    // Set the current branch if it's not main and if it has not been removed from the filters
    setFilters([...filters, { name: branchFilterName, value: currentBranch.name }]);
  }, []);

  return (
    <FilterTag label="branches" currentFilter={currentFilter} {...props}>
      <Popover open={showFilters} onOpenChange={setShowFilters}>
        <PopoverTrigger className="flex h-6 items-center pl-1">
          <span>Branch</span>

          <div className="ml-1 w-px self-stretch bg-gray-300" />

          {currentFilter?.value ? (
            <div
              className="flex h-6 items-center gap-1 rounded-r-full px-1 transition-all hover:bg-gray-300"
              onClick={(event) => {
                event.stopPropagation();
                handleRemoveFilter();
              }}
            >
              <div className="inline-flex items-center font-medium text-custom-blue-700">
                {currentFilter.value}
              </div>

              <Icon
                icon="mdi:close-circle-outline"
                className="text-base text-gray-400 transition-all group-hover:text-custom-blue-700"
              />
            </div>
          ) : (
            <Icon
              icon="mdi:plus-circle-outline"
              className="mx-1 text-base text-gray-400 transition-all group-hover:text-custom-blue-700"
            />
          )}
        </PopoverTrigger>

        <PopoverContent className="relative rounded-tl-none" align="start">
          <div className="-top-[1.8rem] -left-px absolute rounded-t-md border border-gray-200 border-b-0 bg-white px-2 py-1">
            Filter by <span className="ml-1 font-semibold">branch</span>
          </div>

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
            onSuccess={() => {
              setShowFilters(false);
            }}
          />
        </PopoverContent>
      </Popover>
    </FilterTag>
  );
}
