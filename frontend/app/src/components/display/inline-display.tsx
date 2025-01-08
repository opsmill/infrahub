import { Button } from "@/components/buttons/button-primitive";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ReactElement } from "react";

interface InlineDisplayProps {
  items: Array<string>;
  render: (item: string) => ReactElement;
  maxDisplay?: number;
}

export function InlineDisplay({ items, render, maxDisplay = 3 }: InlineDisplayProps) {
  const trimedItems = items.slice(0, maxDisplay);
  const remainingItems = items.slice(maxDisplay);

  return (
    <div className="flex items-center gap-2">
      <div className="flex gap-2 items-center relative">
        {trimedItems.map((item) => {
          return render ? render(item) : item;
        })}
      </div>

      {!!remainingItems?.length && (
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline" size={"icon"}>{`+${remainingItems?.length}`}</Button>
          </PopoverTrigger>

          <PopoverContent align="start">
            <div className="flex flex-col gap-2">
              {remainingItems.map((item) => {
                return render ? render(item) : item;
              })}
            </div>
          </PopoverContent>
        </Popover>
      )}
    </div>
  );
}
