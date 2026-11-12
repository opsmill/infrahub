import { Button, Popover, PopoverTrigger } from "@infrahub/ui";
import { ArrowUpDownIcon } from "lucide-react";

import { CountBadge } from "@/shared/components/buttons/count-badge";

import { useSort } from "@/entities/nodes/sort/ui/hooks/use-sort";
import { SortEditor } from "@/entities/nodes/sort/ui/sort-editor";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

interface SortPickerProps {
  schema: ModelSchema;
  /** How many sort keys the surface can honour; unlimited when absent. */
  maxSorts?: number;
}

export function SortPicker({ schema, maxSorts }: SortPickerProps) {
  const { customSort } = useSort(schema);

  return (
    <PopoverTrigger>
      <Button variant="input" size="sm">
        <ArrowUpDownIcon /> Sort
        {!!customSort?.length && <CountBadge count={customSort.length} />}
      </Button>

      <Popover placement="bottom start">
        <SortEditor schema={schema} maxSorts={maxSorts} />
      </Popover>
    </PopoverTrigger>
  );
}
