import { Button, Popover, PopoverTrigger } from "@infrahub/ui";
import { Columns3Icon } from "lucide-react";

import { CountBadge } from "@/shared/components/buttons/count-badge";

import type { ColumnSurface } from "@/entities/nodes/columns/domain/model/column-surface";
import { ColumnsEditor } from "@/entities/nodes/columns/ui/columns-editor";
import { useColumnVisibility } from "@/entities/nodes/columns/ui/hooks/use-column-visibility";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

interface ColumnsPickerProps {
  schema: ModelSchema;
  surface?: ColumnSurface;
}

/**
 * The toolbar entry point to the column checklist.
 *
 * The badge counts the departures from the surface's default column set rather than the hidden
 * columns: revealing a column customizes the view just as much as hiding one, and it is the same
 * condition that offers the reset control inside the editor.
 */
export function ColumnsPicker({ schema, surface }: ColumnsPickerProps) {
  const { customizedCount } = useColumnVisibility(schema, surface);

  return (
    <PopoverTrigger>
      <Button variant="input" size="sm">
        <Columns3Icon /> Columns
        {customizedCount > 0 && <CountBadge count={customizedCount} />}
      </Button>

      <Popover placement="bottom start">
        <ColumnsEditor schema={schema} surface={surface} />
      </Popover>
    </PopoverTrigger>
  );
}
