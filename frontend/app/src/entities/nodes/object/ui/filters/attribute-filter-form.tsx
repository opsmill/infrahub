import { useState } from "react";

import { getCurrentFilterCondition } from "@/shared/components/filters/utils/get-current-filter-condition";
import type { FormAttributeValue } from "@/shared/components/form/type";
import { FormField } from "@/shared/components/ui/form";
import useFilters, { type Filter } from "@/shared/hooks/useFilters";

import { DateRangePickerFields } from "@/entities/nodes/object/ui/filters/date-range-picker-fields";
import { DynamicFilterInput } from "@/entities/nodes/object/ui/filters/dynamic-filter-input";
import {
  FILTER_CONDITION,
  type FilterCondition,
} from "@/entities/nodes/object/ui/filters/filter-condition-select";
import { FilterFormLayout } from "@/entities/nodes/object/ui/filters/filter-form-layout";
import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import type { AttributeSchema } from "@/entities/schema/types";

export type AttributeFilterFormProps = {
  attributeSchema: AttributeSchema;
  onSuccess?: () => void;
};

export function AttributeFilterForm({ attributeSchema, onSuccess }: AttributeFilterFormProps) {
  const [filters, setFilters] = useFilters();
  const currentFilter = filters.find((filter) => filter.name.startsWith(attributeSchema.name));
  const isDatetime = attributeSchema.kind === ATTRIBUTE_KIND.DATETIME;

  const afterFilterName = `${attributeSchema.name}__after`;
  const beforeFilterName = `${attributeSchema.name}__before`;
  const afterFilter = filters.find((f) => f.name === afterFilterName);
  const beforeFilter = filters.find((f) => f.name === beforeFilterName);

  const toISOString = (value: unknown): string =>
    value instanceof Date ? value.toISOString() : String(value);

  const defaultCondition = isDatetime ? FILTER_CONDITION.AFTER : FILTER_CONDITION.CONTAINS;
  const [condition, setCondition] = useState<FilterCondition>(
    getCurrentFilterCondition(currentFilter) ?? defaultCondition
  );

  const handleSubmit = (formData: Record<string, FormAttributeValue["value"]>) => {
    if (
      isDatetime &&
      (condition === FILTER_CONDITION.AFTER ||
        condition === FILTER_CONDITION.BEFORE ||
        condition === FILTER_CONDITION.BETWEEN)
    ) {
      const { afterDate, beforeDate } = formData as {
        afterDate?: unknown;
        beforeDate?: unknown;
      };
      let newFilters = filters.filter(
        (f) => f.name !== afterFilterName && f.name !== beforeFilterName
      );

      if (
        (condition === FILTER_CONDITION.AFTER || condition === FILTER_CONDITION.BETWEEN) &&
        afterDate
      ) {
        newFilters = [...newFilters, { name: afterFilterName, value: toISOString(afterDate) }];
      }
      if (
        (condition === FILTER_CONDITION.BEFORE || condition === FILTER_CONDITION.BETWEEN) &&
        beforeDate
      ) {
        newFilters = [...newFilters, { name: beforeFilterName, value: toISOString(beforeDate) }];
      }
      return setFilters(newFilters);
    }

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

  return (
    <FilterFormLayout
      filterType={isDatetime ? "datetime" : "attribute"}
      label={attributeSchema.label}
      condition={condition}
      onConditionChange={setCondition}
      testId="attribute-filter-form"
      onSubmit={(formData) => {
        handleSubmit(formData as Record<string, FormAttributeValue["value"]>);
        onSuccess?.();
      }}
    >
      {isDatetime &&
      (condition === FILTER_CONDITION.AFTER ||
        condition === FILTER_CONDITION.BEFORE ||
        condition === FILTER_CONDITION.BETWEEN) ? (
        <DateRangePickerFields
          condition={condition}
          afterDefault={afterFilter?.value as string | undefined}
          beforeDefault={beforeFilter?.value as string | undefined}
        />
      ) : condition === FILTER_CONDITION.CONTAINS ? (
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
      ) : null}
    </FilterFormLayout>
  );
}
