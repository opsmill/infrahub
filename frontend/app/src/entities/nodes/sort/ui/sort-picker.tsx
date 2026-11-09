import { Button, Popover, PopoverTrigger } from "@infrahub/ui";
import { ArrowUpDownIcon } from "lucide-react";

import { CountBadge } from "@/shared/components/buttons/count-badge";

import { useSort } from "@/entities/nodes/sort/ui/hooks/use-sort";
import { SortEditor } from "@/entities/nodes/sort/ui/sort-editor";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

interface SortPickerProps {
  schema: ModelSchema;
}

export function SortPicker({ schema }: SortPickerProps) {
  const { customSort } = useSort(schema);

  return (
    <PopoverTrigger>
      <Button variant="input" size="sm">
        <ArrowUpDownIcon /> Sort
        {!!customSort?.length && <CountBadge count={customSort.length} />}
      </Button>

      <Popover placement="bottom start">
        <SortEditor schema={schema} />
      </Popover>
    </PopoverTrigger>
  );
}
