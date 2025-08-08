import { ActionsHeaderCell } from "@/entities/nodes/object/ui/object-table/cells/actions-header-cell";
import { ObjectActionsCell } from "@/entities/nodes/object/ui/object-table/cells/object-actions-cell";
import { NodeObject } from "@/entities/nodes/types";
import { Permission } from "@/entities/permission/types";
import { ColumnDef, createColumnHelper } from "@tanstack/react-table";

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
