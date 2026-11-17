import type { NodeCore } from "@/entities/nodes/object/domain/model/node";
import { ToolbarGroupsAction } from "@/entities/nodes/object/ui/object-table/toolbar/actions/groups/toolbar-groups-action";
import { removeRelationships } from "@/entities/nodes/relationships/domain/use-cases/remove-relationships";

export interface ToolbarRemoveFromGroupActionProps {
  selectedRows: Array<NodeCore>;
}

export function ToolbarRemoveFromGroupsAction({ selectedRows }: ToolbarRemoveFromGroupActionProps) {
  return (
    <ToolbarGroupsAction
      selectedRows={selectedRows}
      label="Remove from groups"
      variant="danger-outline"
      mutateMembers={removeRelationships}
      groupsQueryFilter={{ members__ids: selectedRows.map((row) => row.id) }}
    />
  );
}
