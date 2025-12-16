import { Icon } from "@iconify-icon/react";

import { Button } from "@/shared/components/buttons/button-primitive";
import useFilters from "@/shared/hooks/useFilters";

const BranchesEmptyText = () => {
  return (
    <>
      <div className="font-medium text-lg">No branches found</div>
      <div className="text-sm">Create a new branche to see it here</div>
    </>
  );
};

export function BranchesEmpty() {
  const [filters, setFilters] = useFilters();

  const handleClearFilters = () => {
    setFilters([]);
  };

  return (
    <div className="col-span-full flex flex-col items-center justify-center py-12 text-stone-500">
      <Icon icon="mdi:source-branch" className="mb-2 text-3xl" />
      {filters.length === 0 ? (
        <BranchesEmptyText />
      ) : (
        <>
          <BranchesEmptyText />
          <Button size="sm" variant="outline" className="mt-4" onClick={handleClearFilters}>
            <Icon icon="mdi:filter-variant-remove" className="mr-1.5" />
            Clear filters
          </Button>
        </>
      )}
    </div>
  );
}
