import { Button } from "@/components/buttons/button-primitive";
import { Badge } from "@/components/ui/badge";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

interface RelationshipDisplayProps {
  items: Array<string>;
}

export function RelationshipDisplay({ items }: RelationshipDisplayProps) {
  const trimedItems = items.slice(0, 3);
  const restOfItems = items.slice(3);

  const lengthDiff = items.length - trimedItems.length;

  return (
    <div className="flex items-center gap-2">
      <div className="flex gap-2 items-center relative">
        {trimedItems.map((item, index) => (
          <Badge key={index}>{item}</Badge>
        ))}
      </div>

      {!!lengthDiff && (
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline" size={"icon"}>{`+${lengthDiff}`}</Button>
          </PopoverTrigger>

          <PopoverContent align="start">
            <div className="flex flex-col gap-2">
              {restOfItems.map((item, index) => (
                <Badge key={index}>{item}</Badge>
              ))}
            </div>
          </PopoverContent>
        </Popover>
      )}
    </div>
  );
}
