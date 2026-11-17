import type { TagProps } from "react-aria-components";

import { useFilters } from "@/entities/nodes/filters/ui/hooks/use-filters";
import type { NodeCore } from "@/entities/nodes/object/domain/model/node";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";

import { EventFilterTag } from "./event-filter-tag";
import { GlobalKindFilterForm } from "./global-kind-filter-form";

interface FilterTagProps extends TagProps {
  label: string;
  name: string;
}

export function GlobalKindFilter({ label, name, ...props }: FilterTagProps) {
  const [filters, setFilters] = useFilters();

  const currentFilter = filters.find((filter) => filter.name.startsWith(name));

  const handleRemoveFilter = (filterName: string) => {
    setFilters(filters.filter((f) => f.name !== `${filterName}__value`));
  };

  const getFilterDisplayValue = () => {
    return currentFilter?.value
      .map((value: NodeCore) => {
        return getNodeLabel(value);
      })
      .join(", ");
  };

  return (
    <EventFilterTag
      label={label}
      currentFilter={currentFilter}
      renderValue={getFilterDisplayValue}
      onRemove={() => handleRemoveFilter(name)}
      renderForm={(close) => <GlobalKindFilterForm name={name} onSuccess={close} />}
      {...props}
    />
  );
}
