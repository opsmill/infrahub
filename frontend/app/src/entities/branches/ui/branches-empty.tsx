import { Icon } from "@iconify-icon/react";

import { Button } from "@/shared/components/ui/button";
import useFilters from "@/shared/hooks/useFilters";

export function BranchesEmpty() {
  const [filters, setFilters] = useFilters();

  const handleClearFilters = () => {
    setFilters([]);
  };

  return (
    <div className="col-span-full flex flex-col items-center justify-center py-12 text-stone-500">
      <Icon icon="mdi:source-branch" className="mb-2 text-3xl" />
      {filters.length === 0 ? (
        <>
          <div className="font-medium text-lg">No branches yet</div>
          <div className="text-sm">Create your first branch to get started</div>
        </>
      ) : (
        <>
          <div className="font-medium text-lg">No matching branches</div>
          <div className="text-sm">Try adjusting or clearing your filters</div>

          <Button size="sm" variant="outline" className="mt-4" onClick={handleClearFilters}>
            <Icon icon="mdi:filter-variant-remove" className="mr-1.5" />
            Clear filters
          </Button>
        </>
      )}
    </div>
  );
}
