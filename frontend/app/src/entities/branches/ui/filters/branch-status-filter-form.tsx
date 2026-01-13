import { useState } from "react";

import { getCurrentFilterCondition } from "@/shared/components/filters/utils/get-current-filter-condition";
import { Form, FormField, FormSubmit } from "@/shared/components/ui/form";
import useFilters, { type Filter } from "@/shared/hooks/useFilters";

import type { BranchStatus } from "@/entities/branches/constants";
import { BRANCH_FIELD_SCHEMAS } from "@/entities/branches/ui/branches-table/branch-field-schemas";
import { BranchStatusEnum } from "@/entities/branches/ui/filters/branch-status-enum";
import {
  FILTER_CONDITION,
  type FilterCondition,
  FilterConditionSelect,
} from "@/entities/nodes/object/ui/filters/filter-condition-select";

export interface BranchStatusFilterFormProps {
  onSuccess?: () => void;
}

export function BranchStatusFilterForm({ onSuccess }: BranchStatusFilterFormProps) {
  const [filters, setFilters] = useFilters();
  const fieldSchema = BRANCH_FIELD_SCHEMAS.status;
  const currentFilter = filters.find((filter) => filter.name.startsWith(fieldSchema.name));
  const [condition, setCondition] = useState<FilterCondition>(
    getCurrentFilterCondition(currentFilter) ?? FILTER_CONDITION.CONTAINS
  );

  const handleSubmit = (formData: Record<string, BranchStatus | null>) => {
    if (condition === FILTER_CONDITION.CONTAINS) {
      const { attribute } = formData;

      if (!attribute) {
        return setFilters(filters.filter((f) => !f.name.startsWith(fieldSchema.name)));
      }

      const newFilter: Filter = {
        name: `${fieldSchema.name}__value`,
        value: attribute,
      };

      if (currentFilter) {
        return setFilters(
          filters.map((f) => (f.name.startsWith(fieldSchema.name) ? newFilter : f))
        );
      } else {
        return setFilters([...filters, newFilter]);
      }
    }

    if (condition === FILTER_CONDITION.IS_EMPTY || condition === FILTER_CONDITION.IS_NOT_EMPTY) {
      return setFilters([
        ...filters.filter((f) => !f.name.startsWith(fieldSchema.name)),
        {
          name: `${fieldSchema.name}__isnull`,
          value: true,
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
          handleSubmit(formData as Record<string, BranchStatus | null>);
          onSuccess?.();
        }}
        data-testid="branch-status-filter-form"
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
            render={({ field }) => (
              <BranchStatusEnum
                value={field.value as BranchStatus | null}
                onChange={field.onChange}
                defaultOpen
              />
            )}
          />
        )}

        <FormSubmit>Apply</FormSubmit>
      </Form>
    </div>
  );
}
