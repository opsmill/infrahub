import { useState } from "react";

import { getCurrentFilterCondition } from "@/shared/components/filters/utils/get-current-filter-condition";
import type { FormAttributeValue } from "@/shared/components/form/type";
import { Form, FormField, FormSubmit } from "@/shared/components/ui/form";
import useFilters, { type Filter } from "@/shared/hooks/useFilters";

import { DynamicFilterInput } from "@/entities/nodes/object/ui/filters/dynamic-filter-input";
import {
  FILTER_CONDITION,
  type FilterCondition,
  FilterConditionSelect,
} from "@/entities/nodes/object/ui/filters/filter-condition-select";
import type { AttributeSchema } from "@/entities/schema/types";

export type AttributeFilterFormProps = {
  attributeSchema: AttributeSchema;
  onSuccess?: () => void;
};

export function AttributeFilterForm({ attributeSchema, onSuccess }: AttributeFilterFormProps) {
  const [filters, setFilters] = useFilters();
  const currentFilter = filters.find((filter) => filter.name.startsWith(attributeSchema.name));
  const [condition, setCondition] = useState<FilterCondition>(
    getCurrentFilterCondition(currentFilter) ?? FILTER_CONDITION.CONTAINS
  );

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
        {condition === FILTER_CONDITION.CONTAINS && (
          <FormField
            name="attribute"
            defaultValue={
              currentFilter &&
              getCurrentFilterCondition(currentFilter) === FILTER_CONDITION.CONTAINS
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
