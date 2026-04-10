import { useState } from "react";
import DateTimePicker from "react-datepicker";

import { FormField } from "@/shared/components/ui/form";
import useFilters, { type Filter } from "@/shared/hooks/useFilters";
import { DATE_TIME_FORMAT } from "@/shared/utils/date";

import type { MetadataDateFilterDefinition } from "@/entities/nodes/object/domain/filter-definition";
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

  const isBetween = condition === FILTER_CONDITION.BETWEEN;
  const showAfter = condition === FILTER_CONDITION.AFTER || isBetween;
  const showBefore = condition === FILTER_CONDITION.BEFORE || isBetween;

  return (
    <FilterFormLayout
      filterType="metadata-date"
      condition={condition}
      onConditionChange={setCondition}
      testId="metadata-date-filter-form"
      onSubmit={handleSubmit}
    >
      <div className={isBetween ? "flex flex-row gap-4" : "flex flex-col gap-0"}>
        {showAfter && (
          <FormField
            name="afterDate"
            defaultValue={afterFilter?.value ?? undefined}
            render={({ field }) => (
              <div className="flex flex-col gap-1">
                {isBetween && <span className="text-gray-600 text-xs">After</span>}
                <DateTimePicker
                  selected={field.value ? new Date(field.value as string) : null}
                  onChange={field.onChange}
                  inline
                  showTimeSelect
                  timeIntervals={1}
                  calendarStartDay={1}
                  dateFormat={DATE_TIME_FORMAT}
                  calendarClassName="flex!"
                />
              </div>
            )}
          />
        )}

        {showBefore && (
          <FormField
            name="beforeDate"
            defaultValue={beforeFilter?.value ?? undefined}
            render={({ field }) => (
              <div className="flex flex-col gap-1">
                {isBetween && <span className="text-gray-600 text-xs">Before</span>}
                <DateTimePicker
                  selected={field.value ? new Date(field.value as string) : null}
                  onChange={field.onChange}
                  inline
                  showTimeSelect
                  timeIntervals={1}
                  calendarStartDay={1}
                  dateFormat={DATE_TIME_FORMAT}
                  calendarClassName="flex!"
                />
              </div>
            )}
          />
        )}
      </div>
    </FilterFormLayout>
  );
}
