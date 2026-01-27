import { useState } from "react";

import { getCurrentFilterCondition } from "@/shared/components/filters/utils/get-current-filter-condition";
import type { FormAttributeValue } from "@/shared/components/form/type";
import { DatePicker } from "@/shared/components/inputs/date-picker";
import { Form, FormField, FormSubmit } from "@/shared/components/ui/form";
import useFilters, { type Filter } from "@/shared/hooks/useFilters";

import { DynamicFilterInput } from "@/entities/nodes/object/ui/filters/dynamic-filter-input";
import {
  FILTER_CONDITION,
  type FilterCondition,
  FilterConditionSelect,
} from "@/entities/nodes/object/ui/filters/filter-condition-select";
import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import type { AttributeSchema } from "@/entities/schema/types";

export type AttributeFilterFormProps = {
  attributeSchema: AttributeSchema;
  onSuccess?: () => void;
};

export function AttributeFilterForm({ attributeSchema, onSuccess }: AttributeFilterFormProps) {
  const [filters, setFilters] = useFilters();
  const currentFilter = filters.find((filter) => filter.name.startsWith(attributeSchema.name));
  const isDateField = attributeSchema.kind === ATTRIBUTE_KIND.DATETIME;
  const defaultCondition = isDateField ? FILTER_CONDITION.AFTER : FILTER_CONDITION.CONTAINS;
  const [condition, setCondition] = useState<FilterCondition>(
    getCurrentFilterCondition(currentFilter) ?? defaultCondition
  );

  // For date range filters
  if (isDateField) {
    return <DateRangeFilterForm attributeSchema={attributeSchema} onSuccess={onSuccess} />;
  }

  const handleSubmit = (formData: Record<string, FormAttributeValue["value"]>) => {
    if (condition === FILTER_CONDITION.CONTAINS) {
      const { attribute } = formData;

      if (!attribute && attribute !== 0 && attribute !== false) {
        return setFilters(filters.filter((f) => !f.name.startsWith(attributeSchema.name)));
      }

      const isAttributeArray = Array.isArray(attribute);
      const newFilter: Filter = {
        name: `${attributeSchema.name}__${isAttributeArray ? "values" : "value"}`,
        value: attribute,
      };

      if (currentFilter) {
        return setFilters(
          filters.map((f) => (f.name.startsWith(attributeSchema.name) ? newFilter : f))
        );
      } else {
        return setFilters([...filters, newFilter]);
      }
    }

    if (condition === FILTER_CONDITION.IS_EMPTY) {
      return setFilters([
        ...filters.filter((f) => f.name !== currentFilter?.name),
        {
          name: `${attributeSchema.name}__isnull`,
          value: true,
        },
      ]);
    }

    if (condition === FILTER_CONDITION.IS_NOT_EMPTY) {
      return setFilters([
        ...filters.filter((f) => f.name !== currentFilter?.name),
        {
          name: `${attributeSchema.name}__isnull`,
          value: false,
        },
      ]);
    }
  };

  const showInput = condition === FILTER_CONDITION.CONTAINS;

  return (
    <div className="flex gap-2 p-2">
      <div className="inline-flex h-10 items-center">Where</div>

      <FilterConditionSelect
        filterType="attribute"
        value={condition}
        onChange={(key) => setCondition(key as FilterCondition)}
      />

      <Form
        className="flex gap-2 space-y-0"
        onSubmit={(formData) => {
          handleSubmit(formData);
          onSuccess?.();
        }}
        data-testid="attribute-filter-form"
      >
        {showInput && (
          <FormField
            name="attribute"
            defaultValue={
              currentFilter && getCurrentFilterCondition(currentFilter) === condition
                ? currentFilter.value
                : undefined
            }
            render={({ field }) => {
              return <DynamicFilterInput {...field} fieldSchema={attributeSchema} />;
            }}
          />
        )}

        <FormSubmit>Apply</FormSubmit>
      </Form>
    </div>
  );
}

function DateRangeFilterForm({ attributeSchema, onSuccess }: AttributeFilterFormProps) {
  const [filters, setFilters] = useFilters();

  const afterFilterName = `${attributeSchema.name}__after`;
  const beforeFilterName = `${attributeSchema.name}__before`;

  const afterFilter = filters.find((f) => f.name === afterFilterName);
  const beforeFilter = filters.find((f) => f.name === beforeFilterName);

  const handleSubmit = (formData: Record<string, string | null>) => {
    const { afterDate, beforeDate } = formData;

    // Remove existing date filters for this field
    let newFilters = filters.filter(
      (f) => f.name !== afterFilterName && f.name !== beforeFilterName
    );

    // Add new filters
    if (afterDate) {
      newFilters = [...newFilters, { name: afterFilterName, value: afterDate }];
    }
    if (beforeDate) {
      newFilters = [...newFilters, { name: beforeFilterName, value: beforeDate }];
    }

    setFilters(newFilters);
    onSuccess?.();
  };

  return (
    <Form
      className="flex flex-col gap-3 p-3"
      onSubmit={(formData) => handleSubmit(formData as Record<string, string | null>)}
      data-testid="date-range-filter-form"
    >
      <div className="flex items-center gap-2">
        <span className="w-14 text-gray-600 text-sm">After</span>
        <FormField
          name="afterDate"
          defaultValue={afterFilter?.value ?? undefined}
          render={({ field }) => (
            <DatePicker
              date={field.value ? new Date(field.value as string) : null}
              onChange={field.onChange}
              showTime={false}
            />
          )}
        />
      </div>

      <div className="flex items-center gap-2">
        <span className="w-14 text-gray-600 text-sm">Before</span>
        <FormField
          name="beforeDate"
          defaultValue={beforeFilter?.value ?? undefined}
          render={({ field }) => (
            <DatePicker
              date={field.value ? new Date(field.value as string) : null}
              onChange={field.onChange}
              showTime={false}
            />
          )}
        />
      </div>

      <FormSubmit className="self-end">Apply</FormSubmit>
    </Form>
  );
}
