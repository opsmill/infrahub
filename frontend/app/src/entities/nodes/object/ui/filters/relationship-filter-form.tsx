import { useState } from "react";

import { getCurrentFilterCondition } from "@/shared/components/filters/utils/get-current-filter-condition";
import { FormField } from "@/shared/components/ui/form";
import useFilters, { type Filter } from "@/shared/hooks/useFilters";

import {
  FILTER_CONDITION,
  type FilterCondition,
} from "@/entities/nodes/object/ui/filters/filter-condition-select";
import { FilterFormLayout } from "@/entities/nodes/object/ui/filters/filter-form-layout";
import { RelationshipFilterCombobox } from "@/entities/nodes/object/ui/filters/relationship-filter-combobox";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import type { RelationshipSchema } from "@/entities/schema/types";

export interface RelationshipFilterFormProps {
  relationshipSchema: RelationshipSchema;
  onSuccess?: () => void;
}

type FormData = {
  relationships: RelationshipNode[];
};

export function RelationshipFilterForm({
  relationshipSchema,
  onSuccess,
}: RelationshipFilterFormProps) {
  const [filters, setFilters] = useFilters();
  const currentFilter = filters.find((filter) => filter.name.startsWith(relationshipSchema.name));
  const [condition, setCondition] = useState<FilterCondition>(
    getCurrentFilterCondition(currentFilter) ?? FILTER_CONDITION.IS_ANY_OF
  );

  const handleSubmit = (data: FormData) => {
    if (condition === FILTER_CONDITION.IS_EMPTY) {
      return setFilters([
        ...filters.filter((f) => f.name !== currentFilter?.name),
        {
          name: `${relationshipSchema.name}__isnull`,
          value: true,
        },
      ]);
    }

    if (condition === FILTER_CONDITION.IS_NOT_EMPTY) {
      return setFilters([
        ...filters.filter((f) => f.name !== currentFilter?.name),
        {
          name: `${relationshipSchema.name}__isnull`,
          value: false,
        },
      ]);
    }

    if (condition === FILTER_CONDITION.IS_ANY_OF) {
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
      } else {
        return setFilters([...filters, newFilter]);
      }
    }
  };

  return (
    <FilterFormLayout
      filterType="relationship"
      condition={condition}
      onConditionChange={setCondition}
      testId="relationship-filter-form"
      onSubmit={(formData) => {
        handleSubmit(formData as FormData);
        onSuccess?.();
      }}
    >
      {condition === FILTER_CONDITION.IS_ANY_OF && (
        <FormField
          name="relationships"
          defaultValue={
            currentFilter && getCurrentFilterCondition(currentFilter) === FILTER_CONDITION.IS_ANY_OF
              ? currentFilter.value
              : undefined
          }
          render={({ field }) => (
            <RelationshipFilterCombobox
              peer={relationshipSchema.peer}
              value={field.value as RelationshipNode[] | undefined}
              onChange={field.onChange}
            />
          )}
        />
      )}
    </FilterFormLayout>
  );
}
