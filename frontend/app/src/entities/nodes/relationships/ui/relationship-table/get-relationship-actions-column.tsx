import { type ColumnDef, createColumnHelper } from "@tanstack/react-table";

import { ActionsHeaderCell } from "@/entities/nodes/object/ui/object-table/cells/actions-header-cell";
import { RelationshipActionsCell } from "@/entities/nodes/relationships/ui/relationship-table/relationship-actions-cell";
import type { NodeObject } from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";

const columnHelper = createColumnHelper<NodeObject>();

export type GetRelationshipActionsColumnParams = {
  parentId: string;
  parentKind: string;
  relationshipName: string;
  permission: Permission;
  relationshipsCount: number;
};

export function getRelationshipActionsColumn({
  parentId,
  parentKind,
  relationshipName,
  permission,
  relationshipsCount,
}: GetRelationshipActionsColumnParams): ColumnDef<NodeObject> {
  return columnHelper.display({
    id: "actions",
    header: () => <ActionsHeaderCell />,
    cell: ({ row }) => {
      return (
        <RelationshipActionsCell
          permission={permission}
          parentId={parentId}
          parentKind={parentKind}
          relationshipName={relationshipName}
          relationshipKind={row.original.__typename}
          relationshipLabel={row.getValue("id")}
          relationshipId={row.original.id}
          relationshipsCount={relationshipsCount}
        />
      );
    },
  });
}
