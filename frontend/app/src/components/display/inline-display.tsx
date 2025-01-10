import { Button } from "@/components/buttons/button-primitive";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ReactElement } from "react";

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
  const trimedItems = items.slice(0, maxDisplay);
  const remainingItems = items.slice(maxDisplay);

  return (
    <div className="flex items-center gap-4">
      <div className="flex gap-2 items-center relative">
        {trimedItems.map((item) => handleRender(item, render))}
      </div>

      {!!remainingItems?.length && (
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline" size={"icon"}>{`+${remainingItems?.length}`}</Button>
          </PopoverTrigger>

          <PopoverContent align="start">
            <div className="flex flex-col gap-2">
              {remainingItems.map((item) => handleRender(item, render))}
            </div>
          </PopoverContent>
        </Popover>
      )}
    </div>
  );
}
