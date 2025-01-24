import useFilters from "@/shared/hooks/useFilters";
import { Icon } from "@iconify-icon/react";
import { Button } from "react-aria-components";

export const ObjectFilterResetButton = () => {
  const [, setFilters] = useFilters();

  const handleResetFilters = () => {
    setFilters([]);
  };

  return (
    <Button
      className="text-neutral-800 rounded-full inline-flex items-center px-2 py-0.5 text-sm hover:bg-gray-100"
      onPress={handleResetFilters}
    >
      <Icon icon="mdi:filter-off-outline" className="mr-1 text-base" />
      Reset filters
    </Button>
  );
};
