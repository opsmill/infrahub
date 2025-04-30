import { ActionsHeaderCell } from "@/entities/nodes/object/ui/object-table/cells/actions-header-cell";
import { RelationshipActionsCell } from "@/entities/nodes/relationships/ui/relationship-table/relationship-actions-cell";
import { NodeObject } from "@/entities/nodes/types";
import { Permission } from "@/entities/permission/types";
import { ColumnDef } from "@tanstack/react-table";

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
  return {
    id: "actions",
    header: () => <ActionsHeaderCell />,
    cell: ({ row }) => {
      return (
        <RelationshipActionsCell
          permission={permission}
          parentId={parentId}
          parentKind={parentKind}
          relationshipName={relationshipName}
          relationshipKind={row.original.__typename as string}
          relationshipLabel={row.getValue("id") as string}
          relationshipId={row.original.id as string}
          relationshipsCount={relationshipsCount}
        />
      );
    },
  };
}
