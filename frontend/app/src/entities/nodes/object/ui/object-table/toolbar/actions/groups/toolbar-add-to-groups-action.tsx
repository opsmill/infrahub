import type { NodeCore } from "@/entities/nodes/object/domain/model/node";
import { ToolbarGroupsAction } from "@/entities/nodes/object/ui/object-table/toolbar/actions/groups/toolbar-groups-action";
import { addRelationships } from "@/entities/nodes/relationships/domain/use-cases/add-relationships";

export interface ToolbarAddToGroupActionProps {
  selectedRows: Array<NodeCore>;
}

export function ToolbarAddToGroupsAction({ selectedRows }: ToolbarAddToGroupActionProps) {
  return (
    <ToolbarGroupsAction
      selectedRows={selectedRows}
      label="Add to groups"
      variant="outline"
      mutateMembers={addRelationships}
      groupsQueryFilter={{ group_type__values: ["default"] }}
    />
  );
}
