import { useState } from "react";
import DateTimePicker from "react-datepicker";

import { FormField } from "@/shared/components/ui/form";
import useFilters, { type Filter } from "@/shared/hooks/useFilters";
import { DATE_TIME_FORMAT } from "@/shared/utils/date";

import { isMetadataDatetimeFilter } from "@/entities/nodes/object/domain/metadata-filter-definitions";
import {
  FILTER_CONDITION,
  type FilterCondition,
} from "@/entities/nodes/object/ui/filters/filter-condition-select";
import { FilterFormLayout } from "@/entities/nodes/object/ui/filters/filter-form-layout";
import { RelationshipFilterCombobox } from "@/entities/nodes/object/ui/filters/relationship-filter-combobox";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

export interface MetadataFilterFormProps {
  metadataFilter: AttributeSchema | RelationshipSchema;
  onSuccess?: () => void;
}

export function MetadataFilterForm({ metadataFilter, onSuccess }: MetadataFilterFormProps) {
  if (isMetadataDatetimeFilter(metadataFilter)) {
    return <MetadataDateFilterForm attributeSchema={metadataFilter} onSuccess={onSuccess} />;
  }

  return <MetadataUserFilterForm relationshipSchema={metadataFilter} onSuccess={onSuccess} />;
}

interface MetadataDateFilterFormProps {
  attributeSchema: AttributeSchema;
  onSuccess?: () => void;
}

function getDefaultDateCondition(afterFilter?: Filter, beforeFilter?: Filter): FilterCondition {
  if (afterFilter && beforeFilter) return FILTER_CONDITION.BETWEEN;
  if (beforeFilter) return FILTER_CONDITION.BEFORE;
  return FILTER_CONDITION.AFTER;
}

function MetadataDateFilterForm({ attributeSchema, onSuccess }: MetadataDateFilterFormProps) {
  const [filters, setFilters] = useFilters();

  const afterFilterName = `${attributeSchema.name}__after`;
  const beforeFilterName = `${attributeSchema.name}__before`;

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

interface MetadataUserFilterFormProps {
  relationshipSchema: RelationshipSchema;
  onSuccess?: () => void;
}

type UserFormData = {
  relationships: RelationshipNode[];
};

function MetadataUserFilterForm({ relationshipSchema, onSuccess }: MetadataUserFilterFormProps) {
  const [filters, setFilters] = useFilters();
  const currentFilter = filters.find((filter) => filter.name.startsWith(relationshipSchema.name));

  const handleSubmit = (data: UserFormData) => {
    const { relationships } = data;

    if (!relationships?.length) {
      return setFilters(filters.filter((f) => !f.name.startsWith(relationshipSchema.name)));
    }

    const newFilter: Filter = {
      name: `${relationshipSchema.name}__ids`,
      value: relationships,
    };

    if (currentFilter) {
      return setFilters(
        filters.map((f) => (f.name.startsWith(relationshipSchema.name) ? newFilter : f))
      );
    }
    return setFilters([...filters, newFilter]);
  };

  return (
    <FilterFormLayout
      filterType="metadata-relationship"
      condition={FILTER_CONDITION.IS_ANY_OF}
      onConditionChange={() => {}}
      testId="metadata-user-filter-form"
      onSubmit={(formData) => {
        handleSubmit(formData as UserFormData);
        onSuccess?.();
      }}
    >
      <FormField
        name="relationships"
        defaultValue={currentFilter?.value ?? undefined}
        render={({ field }) => (
          <RelationshipFilterCombobox
            peer={relationshipSchema.peer}
            value={field.value as RelationshipNode[] | undefined}
            onChange={field.onChange}
          />
        )}
      />
    </FilterFormLayout>
  );
}
