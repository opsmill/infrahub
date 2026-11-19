import { Button, Menu, MenuItem, MenuTrigger, Popover, SubmenuTrigger } from "@infrahub/ui";
import { FilterIcon, XIcon } from "lucide-react";
import type React from "react";

import { SearchInput } from "@/shared/components/inputs/search-input";

import {
  type Facet,
  type ItemFilter,
  isFilterActive,
} from "@/entities/rack-elevation/domain/model/filter";

interface FilterBarProps {
  filter: ItemFilter;
  facets: Facet[];
  matchCount: number;
  totalCount: number;
  onChange: (filter: ItemFilter) => void;
  children?: React.ReactNode;
}

export function FilterBar({
  filter,
  facets,
  matchCount,
  totalCount,
  onChange,
  children,
}: FilterBarProps) {
  const facetLabel = (key: string) => facets.find((facet) => facet.key === key)?.label ?? key;
  const hasCondition = (key: string, value: string) =>
    filter.conditions.some((condition) => condition.key === key && condition.value === value);

  const toggleCondition = (key: string, value: string) =>
    onChange({
      ...filter,
      conditions: hasCondition(key, value)
        ? filter.conditions.filter((c) => !(c.key === key && c.value === value))
        : [...filter.conditions, { key, value }],
    });

  const setFacetValues = (key: string, values: string[]) =>
    onChange({
      ...filter,
      conditions: [
        ...filter.conditions.filter((condition) => condition.key !== key),
        ...values.map((value) => ({ key, value })),
      ],
    });

  return (
    <div className="flex flex-wrap items-center gap-2 border-b px-4 py-2">
      <SearchInput
        className="h-8 w-64"
        placeholder="Search objects in this rack"
        value={filter.query}
        onChange={(query) => onChange({ ...filter, query })}
      />
      <MenuTrigger>
        <Button size="sm" variant="outline">
          <FilterIcon />
          Filter
        </Button>
        <Popover placement="bottom start">
          <Menu aria-label="Filter fields" emptyMessage="No field to filter on">
            {facets.map((facet) => (
              <SubmenuTrigger key={facet.key}>
                <MenuItem textValue={facet.label}>{facet.label}</MenuItem>
                <Popover>
                  <Menu
                    variant="picker"
                    aria-label={`Values of ${facet.label}`}
                    selectionMode="multiple"
                    selectedKeys={facet.values
                      .filter(({ value }) => hasCondition(facet.key, value))
                      .map(({ value }) => value)}
                    onSelectionChange={(keys) =>
                      setFacetValues(
                        facet.key,
                        keys === "all"
                          ? facet.values.map(({ value }) => value)
                          : [...keys].map(String)
                      )
                    }
                  >
                    {facet.values.map(({ value, count }) => (
                      <MenuItem key={value} id={value} textValue={value}>
                        <span className="truncate">{value}</span>
                        <span className="ml-2 text-foreground-muted text-xs tabular-nums">
                          {count}
                        </span>
                      </MenuItem>
                    ))}
                  </Menu>
                </Popover>
              </SubmenuTrigger>
            ))}
          </Menu>
        </Popover>
      </MenuTrigger>

      {filter.conditions.map((condition) => (
        <span
          key={`${condition.key}=${condition.value}`}
          className="flex items-center gap-1 rounded-lg border bg-content-muted py-0.5 pr-0.5 pl-2 text-xs"
        >
          <span className="text-foreground-muted">{facetLabel(condition.key)}:</span>
          {condition.value}
          <Button
            size="xxs"
            shape="square"
            variant="ghost"
            aria-label={`Remove filter ${facetLabel(condition.key)} ${condition.value}`}
            onPress={() => toggleCondition(condition.key, condition.value)}
          >
            <XIcon />
          </Button>
        </span>
      ))}

      {isFilterActive(filter) && (
        <>
          <span className="text-foreground-muted text-xs tabular-nums">
            {matchCount} of {totalCount} objects match
          </span>
          <Button size="xs" variant="ghost" onPress={() => onChange({ query: "", conditions: [] })}>
            Clear
          </Button>
        </>
      )}
      <div className="ml-auto flex gap-2">{children}</div>
    </div>
  );
}
