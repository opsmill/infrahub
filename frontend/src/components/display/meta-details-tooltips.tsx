import React from "react";
import { Property, PropertyList } from "../table/property-list";
import { Icon } from "@iconify-icon/react";
import { Button } from "../buttons/button-primitive";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/popover";

interface MetaDetailsTooltipProps {
  items: Property[];
  header?: React.ReactNode;
}

export default function MetaDetailsTooltip({ header, items }: MetaDetailsTooltipProps) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          size="icon"
          variant="ghost"
          className="text-gray-500 focus-visible:ring-0"
          data-cy="metadata-button"
          data-testid="view-metadata-button">
          <Icon icon="mdi:information-slab-circle-outline" />
        </Button>
      </PopoverTrigger>

      <PopoverContent data-testid="metadata-tooltip" data-cy="metadata-tooltip">
        {!!header && header}

        <PropertyList properties={items} valueClassName="text-right" />
      </PopoverContent>
    </Popover>
  );
}
