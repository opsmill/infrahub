import { FormFieldValue } from "@/shared/components/form/type";
import { Form, FormField, FormSubmit } from "@/shared/components/ui/form";
import { Input } from "@/shared/components/ui/input";
import useFilters from "@/shared/hooks/useFilters";

export type GlobalFilterFormProps = {
  name: string;
  onSuccess?: () => void;
};

export function GlobalFilterForm({ name, onSuccess }: GlobalFilterFormProps) {
  const [filters, setFilters] = useFilters();

  const currentFilter = filters.find((filter) => filter.name.startsWith(name));

  const handleSubmit = ({ filter }: Record<string, FormFieldValue>) => {
    const otherFilters = filters.filter((f) => f.name !== `${name}__value`);

    if (!filter) {
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
    <Form
      className="space-y-0 flex items-center gap-2"
      onSubmit={(formData) => {
        handleSubmit(formData);
      }}
    >
      <FormField
        name="filter"
        defaultValue={currentFilter?.value}
        render={({ field }) => {
          return <Input {...field} />;
        }}
      />

      <FormSubmit>Apply</FormSubmit>
    </Form>
  );
}
