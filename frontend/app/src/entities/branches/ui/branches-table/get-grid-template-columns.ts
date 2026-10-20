import type { ColumnDef } from "@tanstack/react-table";

import { COLUMN_MAX_WIDTH } from "@/shared/components/table/style";

// A column without its own track fits its content up to a cap, so one long value cannot push the table off-screen.
const DEFAULT_GRID_TRACK = `fit-content(${COLUMN_MAX_WIDTH})`;

export function getGridTemplateColumns<TData>(
  columnDefs: readonly Pick<ColumnDef<TData>, "meta">[]
): string {
  return columnDefs.map(({ meta }) => meta?.gridTrack ?? DEFAULT_GRID_TRACK).join(" ");
}
