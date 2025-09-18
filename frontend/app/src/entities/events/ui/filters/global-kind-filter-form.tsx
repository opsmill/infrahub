import { useState } from "react";

import type { FormFieldValue } from "@/shared/components/form/type";
import { Form, FormField, FormSubmit } from "@/shared/components/ui/form";
import useFilters from "@/shared/hooks/useFilters";

import { DynamicFilterInput } from "@/entities/nodes/object/ui/filters/dynamic-filter-input";

import { FilterKindSelect } from "./filter-kind-select";

export type GlobalKindFilterFormProps = {
  name: string;
  onSuccess?: () => void;
};

export function GlobalKindFilterForm({ name, onSuccess }: GlobalKindFilterFormProps) {
  const [filters, setFilters] = useFilters();
  const [kind, setKind] = useState<string | null>(null);

  const currentFilter = filters.find((filter) => filter.name.startsWith(name));

  const handleSubmit = ({ filter }: Record<string, FormFieldValue>) => {
    const otherFilters = filters.filter((f) => f.name !== `${name}__value`);

    if (filter === undefined || filter === null) {
      setFilters(otherFilters);
    } else {
      setFilters([
        ...otherFilters,
        {
          name: `${name}__value`,
          value: filter,
        },
      ]);
    }

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
