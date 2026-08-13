import { Button } from "@infrahub/ui";

import { Icon } from "@/shared/components/display/icon";

import { useFilters } from "@/entities/nodes/filters/ui/hooks/use-filters";

export const FilterResetButton = () => {
  const [, setFilters] = useFilters();

  const handleResetFilters = () => {
    setFilters([]);
  };

  return (
    <Button
      variant="outline"
      size="xs"
      className="sticky right-0 z-10 h-auto rounded-full py-0.5"
      onPress={handleResetFilters}
      data-testid="filter-reset-button"
    >
      <Icon icon="mdi:filter-variant-remove" className="text-base" />
      Clear filters
    </Button>
  );
};
