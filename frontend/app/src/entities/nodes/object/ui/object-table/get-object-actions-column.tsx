import { ActionsHeaderCell } from "@/entities/nodes/object/ui/object-table/cells/actions-header-cell";
import { ObjectActionsCell } from "@/entities/nodes/object/ui/object-table/cells/object-actions-cell";
import { NodeObject } from "@/entities/nodes/types";
import { Permission } from "@/entities/permission/types";
import { ColumnDef } from "@tanstack/react-table";

export function getObjectActionsColumn(permission: Permission): ColumnDef<NodeObject> {
  return {
    id: "actions",
    header: () => <ActionsHeaderCell />,
    cell: ({ row }) => {
      return (
        <ObjectActionsCell
          permission={permission}
          objectKind={row.original.__typename as string}
          objectLabel={row.getValue("id") as string}
          objectId={row.original.id as string}
        />
      );
    },
  };
}
