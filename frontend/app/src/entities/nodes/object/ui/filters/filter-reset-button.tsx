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
        "inline-flex items-center whitespace-nowrap rounded-full border border-transparent px-2 py-0.5 text-neutral-800 text-sm",
        "data-hovered:bg-gray-100"
      )}
      onPress={handleResetFilters}
    >
      <Icon icon="mdi:filter-variant-remove" className="mr-1 text-base" />
      Clear filters
    </Button>
  );
};
