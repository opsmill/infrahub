import { useState } from "react";

import type { FormFieldValue } from "@/shared/components/form/type";
import { Form, FormField, FormSubmit } from "@/shared/components/ui/form";

import { useFilters } from "@/entities/nodes/filters/ui/hooks/use-filters";
import { DynamicFilterInput } from "@/entities/nodes/object/ui/filters/dynamic-filter-input";

import { FilterKindSelect } from "./filter-kind-select";
import { useApplyEventFilter } from "./use-apply-event-filter";

export type GlobalKindFilterFormProps = {
  name: string;
  onSuccess?: () => void;
};

export function GlobalKindFilterForm({ name, onSuccess }: GlobalKindFilterFormProps) {
  const [filters] = useFilters();
  const applyFilter = useApplyEventFilter(name);
  const [kind, setKind] = useState<string | null>(null);

  const currentFilter = filters.find((filter) => filter.name.startsWith(name));

  const handleSubmit = ({ filter }: Record<string, FormFieldValue>) => {
    applyFilter(filter);
    onSuccess?.();
  };

  return (
    <div className="flex items-center gap-2">
      <FilterKindSelect value={kind} onChange={(value) => setKind(value)} />

      {kind && (
        <Form
          className="flex items-center gap-2 space-y-0"
          onSubmit={(formData) => {
            handleSubmit(formData);
          }}
        >
          <FormField
            name="filter"
            defaultValue={currentFilter?.value}
            render={({ field }) => {
              return <DynamicFilterInput {...field} fieldSchema={{ peer: kind }} />;
            }}
          />

          <FormSubmit>Apply</FormSubmit>
        </Form>
      )}
    </div>
  );
}
