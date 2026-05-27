import { Icon } from "@iconify-icon/react";
import { Button } from "@infrahub/ui";
import { useState } from "react";
import type { TagProps } from "react-aria-components";

import { List } from "@/shared/components/inputs/list";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import useFilters from "@/shared/hooks/useFilters";

import { FilterTag } from "@/entities/events/ui/filters/global-filter-tag";

const FILTER_NAME = "eventTypeFilter" as const;
const FILTER_KEY = `${FILTER_NAME}__value` as const;

type AutoCreateFilterValue = {
  group_auto_create?: {
    idp?: string[];
    protocol?: string[];
  };
};

function getDisplayValue(value: AutoCreateFilterValue | undefined): string | undefined {
  const idp = value?.group_auto_create?.idp ?? [];
  const protocol = value?.group_auto_create?.protocol ?? [];
  const parts = [...idp, ...protocol];

  return parts.length > 0 ? parts.join(", ") : undefined;
}

export function GlobalAutoCreateFilter({ ...props }: TagProps) {
  const [filters, setFilters] = useFilters();
  const [showFilters, setShowFilters] = useState(false);

  const currentFilter = filters.find((filter) => filter.name === FILTER_KEY);
  const currentValue = currentFilter?.value as AutoCreateFilterValue | undefined;

  const [idp, setIdp] = useState<string[]>(currentValue?.group_auto_create?.idp ?? []);
  const [protocol, setProtocol] = useState<string[]>(
    currentValue?.group_auto_create?.protocol ?? []
  );

  const otherFilters = () => filters.filter((filter) => filter.name !== FILTER_KEY);

  const handleRemoveFilter = () => {
    setIdp([]);
    setProtocol([]);
    setFilters(otherFilters());
  };

  const handleApply = () => {
    if (idp.length === 0 && protocol.length === 0) {
      setFilters(otherFilters());
    } else {
      setFilters([
        ...otherFilters(),
        {
          name: FILTER_KEY,
          value: {
            group_auto_create: {
              ...(idp.length > 0 && { idp }),
              ...(protocol.length > 0 && { protocol }),
            },
          },
        },
      ]);
    }

    setShowFilters(false);
  };

  const displayValue = getDisplayValue(currentValue);

  return (
    <FilterTag label="Auto-create" currentFilter={currentFilter} {...props}>
      <Popover open={showFilters} onOpenChange={setShowFilters}>
        <PopoverTrigger className="flex h-6 items-center pl-1">
          <span>Auto-create</span>

          <div className="ml-1 w-px self-stretch bg-gray-300" />

          {displayValue ? (
            <div
              className="flex h-6 items-center gap-1 rounded-r-full px-1 transition-all hover:bg-gray-300"
              onClick={(event) => {
                event.stopPropagation();
                handleRemoveFilter();
              }}
            >
              <div className="inline-flex max-w-50 items-center truncate font-medium text-custom-blue-700">
                {displayValue}
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
          <div className="absolute -top-[1.8rem] -left-px rounded-t-md border border-gray-200 border-b-0 bg-white px-2 py-1">
            Filter by <span className="ml-1 font-semibold">auto-create</span>
          </div>

          <div className="flex w-64 flex-col gap-3">
            <div className="flex flex-col gap-1 text-gray-600 text-sm">
              <span>Identity provider</span>
              <List value={idp} onChange={setIdp} />
            </div>

            <div className="flex flex-col gap-1 text-gray-600 text-sm">
              <span>Protocol</span>
              <List value={protocol} onChange={setProtocol} />
            </div>

            <Button className="self-end" onPress={handleApply}>
              Apply
            </Button>
          </div>
        </PopoverContent>
      </Popover>
    </FilterTag>
  );
}
