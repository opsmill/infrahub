import { Button, Popover, PopoverTrigger } from "@infrahub/ui";
import { ArrowUpDownIcon } from "lucide-react";

import { CountBadge } from "@/shared/components/count-badge";

import { SortEditor } from "@/entities/nodes/object/ui/sort/sort-editor";
import { useSort } from "@/entities/nodes/object/ui/sort/use-sort";
import type { ModelSchema } from "@/entities/schema/types";

interface SortPickerProps {
  schema: ModelSchema;
}

export function SortPicker({ schema }: SortPickerProps) {
  const [sort] = useSort(schema);

  return (
    <PopoverTrigger>
      <Button variant="outline" size="sm" className="rounded-xl">
        <ArrowUpDownIcon /> Sort
        {sort !== null && sort.length > 0 && <CountBadge count={sort.length} />}
      </Button>

      <Popover placement="bottom start">
        <SortEditor schema={schema} />
      </Popover>
    </PopoverTrigger>
  );
}
