import type { TagProps } from "react-aria-components";

import { useFilters } from "@/entities/nodes/filters/ui/hooks/use-filters";
import type { NodeCore } from "@/entities/nodes/object/domain/model/node";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";

import { EventFilterTag } from "./event-filter-tag";
import { GlobalKindFilterForm } from "./global-kind-filter-form";
import { useApplyEventFilter } from "./use-apply-event-filter";

interface FilterTagProps extends TagProps {
  label: string;
  name: string;
}

export function GlobalKindFilter({ label, name, ...props }: FilterTagProps) {
  const [filters] = useFilters();
  const applyFilter = useApplyEventFilter(name);

  const currentFilter = filters.find((filter) => filter.name.startsWith(name));

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
      onRemove={() => applyFilter(null)}
      renderForm={(close) => <GlobalKindFilterForm name={name} onSuccess={close} />}
      {...props}
    />
  );
}
