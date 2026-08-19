import { useState } from "react";

import useFilters, { type Filter } from "@/shared/hooks/useFilters";

import type { MetadataDateFilterDefinition } from "@/entities/nodes/object/domain/filter-definition";
import { DateRangePickerFields } from "@/entities/nodes/object/ui/filters/date-range-picker-fields";
import {
  FILTER_CONDITION,
  type FilterCondition,
} from "@/entities/nodes/object/ui/filters/filter-condition-select";
import { FilterFormLayout } from "@/entities/nodes/object/ui/filters/filter-form-layout";

export interface DateMetadataFilterFormProps {
  definition: MetadataDateFilterDefinition;
  onSuccess?: () => void;
}

function getDefaultDateCondition(afterFilter?: Filter, beforeFilter?: Filter): FilterCondition {
  if (afterFilter && beforeFilter) return FILTER_CONDITION.BETWEEN;
  if (beforeFilter) return FILTER_CONDITION.BEFORE;
  return FILTER_CONDITION.AFTER;
}

export function DateMetadataFilterForm({ definition, onSuccess }: DateMetadataFilterFormProps) {
  const [filters, setFilters] = useFilters();

  const afterFilterName = `${definition.name}__after`;
  const beforeFilterName = `${definition.name}__before`;

  const afterFilter = filters.find((f) => f.name === afterFilterName);
  const beforeFilter = filters.find((f) => f.name === beforeFilterName);

  const [condition, setCondition] = useState<FilterCondition>(
    getDefaultDateCondition(afterFilter, beforeFilter)
  );

  const toISOString = (value: unknown): string => {
    return value instanceof Date ? value.toISOString() : String(value);
  };

  const handleSubmit = (formData: Record<string, unknown>) => {
    const { afterDate, beforeDate } = formData;

    let newFilters = filters.filter(
      (f) => f.name !== afterFilterName && f.name !== beforeFilterName
    );

    if (condition === FILTER_CONDITION.AFTER && afterDate) {
      newFilters = [...newFilters, { name: afterFilterName, value: toISOString(afterDate) }];
    }

    if (condition === FILTER_CONDITION.BEFORE && beforeDate) {
      newFilters = [...newFilters, { name: beforeFilterName, value: toISOString(beforeDate) }];
    }

    if (condition === FILTER_CONDITION.BETWEEN) {
      if (afterDate) {
        newFilters = [...newFilters, { name: afterFilterName, value: toISOString(afterDate) }];
      }
      if (beforeDate) {
        newFilters = [...newFilters, { name: beforeFilterName, value: toISOString(beforeDate) }];
      }
    }

    setFilters(newFilters);
    onSuccess?.();
  };

  return (
    <FilterFormLayout
      filterType="metadata-date"
      label={definition.label}
      condition={condition}
      onConditionChange={setCondition}
      testId="metadata-date-filter-form"
      onSubmit={handleSubmit}
    >
      <DateRangePickerFields
        condition={condition}
        afterDefault={afterFilter?.value as string | undefined}
        beforeDefault={beforeFilter?.value as string | undefined}
      />
    </FilterFormLayout>
  );
}
