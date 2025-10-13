import { type ColumnDef, createColumnHelper } from "@tanstack/react-table";

import { ActionsHeaderCell } from "@/entities/nodes/object/ui/object-table/cells/actions-header-cell";
import { ObjectActionsCell } from "@/entities/nodes/object/ui/object-table/cells/object-actions-cell";
import type { NodeObject } from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";

const columnHelper = createColumnHelper<NodeObject>();

export function getObjectActionsColumn(permission: Permission): ColumnDef<NodeObject> {
  return columnHelper.display({
    id: "actions",
    header: () => <ActionsHeaderCell />,
    cell: ({ row }) => {
      return (
        <ObjectActionsCell
          permission={permission}
          objectKind={row.original.__typename}
          objectLabel={row.getValue("id")}
          objectId={row.original.id}
        />
      );
    },
  });
}
