import { Icon } from "@iconify-icon/react";
import { Button } from "react-aria-components";

import { focusVisibleStyle } from "@/shared/components/style-rac";
import useFilters from "@/shared/hooks/useFilters";
import { classNames } from "@/shared/utils/common";

export const FilterResetButton = () => {
  const [, setFilters] = useFilters();

  const handleResetFilters = () => {
    setFilters([]);
  };

  return (
    <Button
      className={classNames(
        focusVisibleStyle,
        "text-neutral-800 whitespace-nowrap rounded-full inline-flex items-center px-2 py-0.5 text-sm border border-transparent",
        "data-hovered:bg-gray-100"
      )}
      onPress={handleResetFilters}
    >
      <Icon icon="mdi:filter-variant-remove" className="mr-1 text-base" />
      Clear filters
    </Button>
  );
};
