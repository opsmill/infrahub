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
 * columns: revealing a column customizes the view just as much as hiding one.
 *
 * It counts only the departures the trust boundary kept, so a param naming a field this schema does
 * not have shows nothing here — there is no column on screen to point at. Whether there is a param
 * left to clear is a different question, which is why the editor gates its reset control on the raw
 * params instead.
 */
export function ColumnsPicker({ schema, surface }: ColumnsPickerProps) {
  const { customizedColumnCount } = useColumnVisibility(schema, surface);

  return (
    <PopoverTrigger>
      <Button variant="input" size="sm">
        <Columns3Icon /> Columns
        {customizedColumnCount > 0 && <CountBadge count={customizedColumnCount} />}
      </Button>

      <Popover placement="bottom start">
        <ColumnsEditor schema={schema} surface={surface} />
      </Popover>
    </PopoverTrigger>
  );
}
