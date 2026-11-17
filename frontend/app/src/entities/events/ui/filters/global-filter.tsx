import type { TagProps } from "react-aria-components";

import { useFilters } from "@/entities/nodes/filters/ui/hooks/use-filters";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import type { FilterFieldSchema } from "@/entities/schema/domain/model/schema";

import { EventFilterTag } from "./event-filter-tag";
import { GlobalFilterForm } from "./global-filter-form";

interface FilterTagProps extends TagProps {
  label: string;
  name: string;
  fieldSchema: FilterFieldSchema;
}

export function GlobalFilter({ label, name, fieldSchema, ...props }: FilterTagProps) {
  const [filters, setFilters] = useFilters();

  const currentFilter = filters.find((filter) => filter.name.startsWith(name));

  const handleRemoveFilter = (filterName: string) => {
    setFilters(filters.filter((f) => f.name !== `${filterName}__value`));
  };

  const getFilterDisplayValue = () => {
    if (typeof currentFilter?.value === "boolean") {
      return JSON.stringify(currentFilter?.value);
    }

    if (fieldSchema.kind === "Dropdown") {
      return fieldSchema.choices?.find((choice) => {
        return choice.name === currentFilter?.value;
      })?.label;
    }

    if (Array.isArray(currentFilter?.value)) {
      return currentFilter?.value
        .map((value) => {
          return getNodeLabel(value);
        })
        .join(", ");
    }

    return currentFilter?.value;
  };

  return (
    <EventFilterTag
      label={label}
      currentFilter={currentFilter}
      renderValue={getFilterDisplayValue}
      onRemove={() => handleRemoveFilter(name)}
      renderForm={(close) => (
        <GlobalFilterForm name={name} fieldSchema={fieldSchema} onSuccess={close} />
      )}
      {...props}
    />
  );
}
