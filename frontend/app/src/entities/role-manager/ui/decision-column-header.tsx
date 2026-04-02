import { Icon } from "@iconify-icon/react";
import { useState } from "react";

import { Select, SelectItem, SelectList, SelectTrigger } from "@/shared/components/aria/select";
import { getCurrentFilterCondition } from "@/shared/components/filters/utils/get-current-filter-condition";
import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { Button } from "@/shared/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import useFilters from "@/shared/hooks/useFilters";
import { classNames } from "@/shared/utils/common";

import {
  FILTER_CONDITION,
  type FilterCondition,
  FilterConditionSelect,
} from "@/entities/nodes/object/ui/filters/filter-condition-select";
import { globalDecisionOptions } from "@/entities/role-manager/constants";
import type { AttributeSchema } from "@/entities/schema/types";
import { FieldSchemaIcon } from "@/entities/schema/ui/field-schema-icon";

const DECISION_OPTIONS = globalDecisionOptions.map((option) => ({
  key: option.value.toString(),
  label: option.label,
  numericValue: option.value,
}));

export function DecisionColumnHeader({ attributeSchema }: { attributeSchema: AttributeSchema }) {
  const [filters, setFilters] = useFilters();
  const [showFilters, setShowFilters] = useState(false);
  const currentFilter = filters.find((f) => f.name.startsWith(attributeSchema.name));
  const [condition, setCondition] = useState<FilterCondition>(
    getCurrentFilterCondition(currentFilter) ?? FILTER_CONDITION.CONTAINS
  );
  const [selectedValue, setSelectedValue] = useState<string | null>(() => {
    if (currentFilter && getCurrentFilterCondition(currentFilter) === FILTER_CONDITION.CONTAINS) {
      return String(currentFilter.value);
    }
    return null;
  });

  const handleApply = () => {
    const cleanedFilters = filters.filter((f) => !f.name.startsWith(attributeSchema.name));

    if (condition === FILTER_CONDITION.CONTAINS && selectedValue) {
      const option = DECISION_OPTIONS.find((o) => o.key === selectedValue);
      if (option) {
        setFilters([
          ...cleanedFilters,
          { name: `${attributeSchema.name}__value`, value: option.numericValue },
        ]);
      }
    } else if (condition === FILTER_CONDITION.IS_EMPTY) {
      setFilters([...cleanedFilters, { name: `${attributeSchema.name}__isnull`, value: true }]);
    } else if (condition === FILTER_CONDITION.IS_NOT_EMPTY) {
      setFilters([...cleanedFilters, { name: `${attributeSchema.name}__isnull`, value: false }]);
    }

    setShowFilters(false);
  };

  return (
    <Popover open={showFilters} onOpenChange={setShowFilters}>
      <PopoverTrigger className={classNames(cellsStyle, cellHeaderStyle)}>
        <FieldSchemaIcon fieldSchema={attributeSchema} />

        <span className="mr-2 truncate">{attributeSchema.label ?? attributeSchema.name}</span>
        <Icon
          icon="mdi:filter-variant"
          className={classNames("ml-auto text-lg", currentFilter ? "text-indigo-700" : "invisible")}
        />
      </PopoverTrigger>

      <PopoverContent className="relative rounded-tl-none p-0" align="start">
        <div className="absolute -top-[1.8rem] -left-px rounded-t-md border border-gray-200 border-b-0 bg-white px-2 py-1 font-semibold">
          Filter by {attributeSchema.label ?? attributeSchema.name}
        </div>

        <div className="flex gap-2 p-2">
          <div className="inline-flex h-10 items-center">Where</div>

          <FilterConditionSelect
            filterType="attribute"
            value={condition}
            onChange={(key) => setCondition(key as FilterCondition)}
          />

          {condition === FILTER_CONDITION.CONTAINS && (
            <Select
              aria-label="select a decision"
              placeholder=""
              value={selectedValue}
              onChange={(key) => setSelectedValue(key as string)}
            >
              <SelectTrigger className="w-33" />
              <SelectList items={DECISION_OPTIONS}>
                {(item) => <SelectItem id={item.key}>{item.label}</SelectItem>}
              </SelectList>
            </Select>
          )}

          <Button onClick={handleApply}>Apply</Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
