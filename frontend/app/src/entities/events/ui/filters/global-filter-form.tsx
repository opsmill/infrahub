import type { FormFieldValue } from "@/shared/components/form/type";
import { Form, FormField, FormSubmit } from "@/shared/components/ui/form";
import useFilters from "@/shared/hooks/useFilters";

import { DynamicFilterInput } from "@/entities/nodes/object/ui/filters/dynamic-filter-input";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

export type GlobalFilterFormProps = {
  name: string;
  fieldSchema: AttributeSchema | RelationshipSchema;
  onSuccess?: () => void;
};

export function GlobalFilterForm({ name, fieldSchema, onSuccess }: GlobalFilterFormProps) {
  const [filters, setFilters] = useFilters();

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
    <div className="flex min-w-64 items-center gap-4">
      <Form
        className="flex grow items-center gap-2 space-y-0"
        onSubmit={(formData) => {
          handleSubmit(formData);
        }}
      >
        <FormField
          name="filter"
          defaultValue={currentFilter?.value}
          render={({ field }) => {
            return <DynamicFilterInput {...field} fieldSchema={fieldSchema} />;
          }}
        />

        <FormSubmit>Apply</FormSubmit>
      </Form>
    </div>
  );
}
