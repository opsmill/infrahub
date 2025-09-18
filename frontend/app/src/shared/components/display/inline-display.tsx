import { type ReactElement, useState } from "react";

import { Button } from "@/shared/components/buttons/button-primitive";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import { debounce } from "@/shared/utils/common";

type Item = string | Record<string, string>;

type Render = (item: Item) => ReactElement | null;

interface InlineDisplayProps {
  items: Array<Item>;
  render: Render;
  maxDisplay?: number;
}

const handleRender = (item: Item, render: Render) => {
  if (typeof item === "string") {
    return render ? render(item) : item;
  }

  if (render) {
    return render(item);
  }

  return null;
};

export function InlineDisplay({ items, render, maxDisplay = 3 }: InlineDisplayProps) {
  const [isOpen, setIsOpen] = useState(false);

  const trimedItems = items.slice(0, maxDisplay);
  const remainingItems = items.slice(maxDisplay);

  const handleMouseEnter = () => {
    setIsOpen(true);
  };

  const handleMouseLeave = () => {
    setIsOpen(false);
  };

  return (
    <div className="flex items-center gap-4">
      <div className="relative flex items-center gap-2">
        {trimedItems.map((item) => handleRender(item, render))}
      </div>

      {!!remainingItems?.length && (
        <Popover open={isOpen}>
          <PopoverTrigger
            asChild
            onMouseEnter={debounce(handleMouseEnter, 200)}
            onMouseLeave={debounce(handleMouseLeave, 200)}
          >
            <Button variant="outline" size={"icon"}>{`+${remainingItems?.length}`}</Button>
          </PopoverTrigger>

          <PopoverContent
            align="start"
            onMouseEnter={debounce(handleMouseEnter, 200)}
            onMouseLeave={debounce(handleMouseLeave, 200)}
            onClick={(event) => {
              event.preventDefault();
            }}
          >
            <div className="flex flex-col gap-2">
              {remainingItems.map((item) => handleRender(item, render))}
            </div>
          </PopoverContent>
        </Popover>
      )}
    </div>
  );
}
