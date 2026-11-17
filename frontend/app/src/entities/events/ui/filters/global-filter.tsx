import type { TagProps } from "react-aria-components";

import { useFilters } from "@/entities/nodes/filters/ui/hooks/use-filters";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import type { FilterFieldSchema } from "@/entities/schema/domain/model/schema";

import { EventFilterTag } from "./event-filter-tag";
import { GlobalFilterForm } from "./global-filter-form";
import { useApplyEventFilter } from "./use-apply-event-filter";

interface FilterTagProps extends TagProps {
  label: string;
  name: string;
  fieldSchema: FilterFieldSchema;
}

export function GlobalFilter({ label, name, fieldSchema, ...props }: FilterTagProps) {
  const [filters] = useFilters();
  const applyFilter = useApplyEventFilter(name);

  const currentFilter = filters.find((filter) => filter.name.startsWith(name));

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
      onRemove={() => applyFilter(null)}
      renderForm={(close) => (
        <GlobalFilterForm name={name} fieldSchema={fieldSchema} onSuccess={close} />
      )}
      {...props}
    />
  );
}
