import { Button, Popover, PopoverDialog, Tooltip } from "@infrahub/ui";
import { DialogTrigger } from "react-aria-components";

import { queryClient } from "@/shared/api/rest/client";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { BulkMutateGroups } from "@/entities/nodes/object/ui/object-table/toolbar/actions/groups/bulk-mutate-groups";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import { addRelationships } from "@/entities/nodes/relationships/domain/add-relationships/add-relationships";
import type { NodeCore } from "@/entities/nodes/types";

export interface ToolbarAddToGroupActionProps {
  selectedRows: Array<NodeCore>;
}

export function ToolbarAddToGroupsAction({ selectedRows }: ToolbarAddToGroupActionProps) {
  const { currentBranch } = useCurrentBranch();
  const { permission } = useObjectTableContext();
  const { isAllowed, message } = permission.update;

  if (!isAllowed) {
    return (
      <Tooltip message={message}>
        <Button variant="outline" size="xs" isDisabledAndFocusable>
          Add to groups
        </Button>
      </Tooltip>
    );
  }

  return (
    <DialogTrigger>
      <Button variant="outline" size="xs">
        Add to groups
      </Button>

      <Popover placement="top start" className="bg-white">
        <PopoverDialog>
          {({ close }) => {
            return (
              <BulkMutateGroups
                mutationFn={async (group) => {
                  await addRelationships({
                    objectId: group.id,
                    relationshipName: "members",
                    relationshipIds: selectedRows.map((row) => row.id),
                    branchName: currentBranch.name,
                  });
                }}
                onSuccess={async () => {
                  await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
                }}
                onClose={close}
                groupsQueryFilter={{ group_type__values: ["default"] }}
              />
            );
          }}
        </PopoverDialog>
      </Popover>
    </DialogTrigger>
  );
}
