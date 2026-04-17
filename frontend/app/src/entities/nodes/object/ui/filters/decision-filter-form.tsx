import { useState } from "react";

import { Select, SelectItem, SelectList, SelectTrigger } from "@/shared/components/aria/select";
import { getCurrentFilterCondition } from "@/shared/components/filters/utils/get-current-filter-condition";
import { FormField } from "@/shared/components/ui/form";
import useFilters, { type Filter } from "@/shared/hooks/useFilters";

import {
  FILTER_CONDITION,
  type FilterCondition,
} from "@/entities/nodes/object/ui/filters/filter-condition-select";
import { FilterFormLayout } from "@/entities/nodes/object/ui/filters/filter-form-layout";
import type { DecisionOption } from "@/entities/role-manager/domain/get-decision-options";
import type { AttributeSchema } from "@/entities/schema/types";

export interface DecisionFilterFormProps {
  attributeSchema: AttributeSchema;
  options: DecisionOption[];
  onSuccess?: () => void;
}

export function DecisionFilterForm({
  attributeSchema,
  options,
  onSuccess,
}: DecisionFilterFormProps) {
  const [filters, setFilters] = useFilters();
  const currentFilter = filters.find((f) => f.name.startsWith(attributeSchema.name));
  const [condition, setCondition] = useState<FilterCondition>(
    getCurrentFilterCondition(currentFilter) ?? FILTER_CONDITION.CONTAINS
  );

  const handleSubmit = (formData: Record<string, unknown>) => {
    const cleanedFilters = filters.filter((f) => !f.name.startsWith(attributeSchema.name));

    if (condition === FILTER_CONDITION.CONTAINS) {
      const raw = formData.decision;
      if (raw === undefined || raw === null || raw === "") {
        setFilters(cleanedFilters);
        return;
      }
      const numericValue = typeof raw === "number" ? raw : Number(raw);
      const newFilter: Filter = {
        name: `${attributeSchema.name}__value`,
        value: numericValue,
      };
      setFilters([...cleanedFilters, newFilter]);
      return;
    }

    if (condition === FILTER_CONDITION.IS_EMPTY) {
      setFilters([...cleanedFilters, { name: `${attributeSchema.name}__isnull`, value: true }]);
      return;
    }

    if (condition === FILTER_CONDITION.IS_NOT_EMPTY) {
      setFilters([...cleanedFilters, { name: `${attributeSchema.name}__isnull`, value: false }]);
      return;
    }
  };

  const defaultValue =
    currentFilter && getCurrentFilterCondition(currentFilter) === FILTER_CONDITION.CONTAINS
      ? Number(currentFilter.value)
      : undefined;

  return (
    <FilterFormLayout
      filterType="permission-decision"
      label={attributeSchema.label}
      condition={condition}
      onConditionChange={setCondition}
      testId="decision-filter-form"
      onSubmit={(formData) => {
        handleSubmit(formData);
        onSuccess?.();
      }}
    >
      {condition === FILTER_CONDITION.CONTAINS && (
        <FormField
          name="decision"
          defaultValue={defaultValue}
          render={({ field }) => (
            <Select
              aria-label="select a decision"
              placeholder="Select a decision"
              value={field.value ?? null}
              onChange={(key) => field.onChange(key)}
            >
              <SelectTrigger className="min-w-40 rounded-xl" />

              <SelectList items={options}>
                {(item) => <SelectItem id={item.value}>{item.label}</SelectItem>}
              </SelectList>
            </Select>
          )}
        />
      )}
    </FilterFormLayout>
  );
}
