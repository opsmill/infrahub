import { Popover } from "@headlessui/react";
import React, { useState } from "react";
import { usePopper } from "react-popper";
import { Property, PropertyList } from "../table/property-list";
import { Icon } from "@iconify-icon/react";
import { Card } from "../ui/card";
import { Button } from "../buttons/button-primitive";

interface MetaDetailsTooltipProps {
  items: Property[];
  header?: React.ReactNode;
}

export default function MetaDetailsTooltip({ header, items }: MetaDetailsTooltipProps) {
  let [referenceElement, setReferenceElement] = useState<HTMLButtonElement | null>();
  let [popperElement, setPopperElement] = useState<HTMLDivElement | null>();
  let { styles, attributes } = usePopper(referenceElement, popperElement, {
    modifiers: [
      {
        name: "flip",
      },
    ],
  });

  // TODO: use the popover component
  return (
    <Popover>
      <Popover.Button
        data-testid="view-metadata-button"
        ref={setReferenceElement}
        as={Button}
        size="icon"
        variant="ghost"
        className="text-gray-500 focus-visible:ring-0"
        data-cy="metadata-button">
        <Icon icon="mdi:information-slab-circle-outline" />
      </Popover.Button>

      <Popover.Panel
        ref={setPopperElement}
        style={styles.popper}
        {...attributes.popper}
        data-testid="metadata-tooltip"
        data-cy="metadata-tooltip">
        <Card className="text-sm divide-y shadow-xl">
          {!!header && header}

          <PropertyList properties={items} valueClassName="text-right" />
        </Card>
      </Popover.Panel>
    </Popover>
  );
}
