import { Icon } from "@iconify-icon/react";

import { Button } from "@/shared/components/buttons/button-primitive";
import useFilters from "@/shared/hooks/useFilters";

import type { ModelSchema } from "@/entities/schema/types";

type ObjectTableEmptyProps =
  | { schema: ModelSchema; label?: never }
  | { schema?: never; label: string };

export function ObjectTableEmpty({ schema, label }: ObjectTableEmptyProps) {
  const [filters, setFilters] = useFilters();
  const schemaLabel = label ?? schema?.label ?? schema?.name ?? "items";

  const handleClearFilters = () => {
    setFilters([]);
  };

  return (
    <div className="col-span-full flex flex-col items-center justify-center py-12 text-stone-500">
      <Icon icon="mdi:table-off" className="mb-2 text-3xl" />
      {filters.length === 0 ? (
        <>
          <div className="font-medium text-lg">No {schemaLabel} found</div>
          <div className="text-sm">Add some {schemaLabel} to get started</div>
        </>
      ) : (
        <>
          <div className="font-medium text-lg">No {schemaLabel} found</div>
          <div className="text-sm">No {schemaLabel} matches the current filters</div>
          <Button size="sm" variant="outline" className="mt-4" onClick={handleClearFilters}>
            <Icon icon="mdi:filter-variant-remove" className="mr-1.5" />
            Clear filters
          </Button>
        </>
      )}
    </div>
  );
}
