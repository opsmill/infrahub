import { Button, Popover, PopoverDialog, Tooltip } from "@infrahub/ui";
import { DialogTrigger } from "react-aria-components";

import { queryClient } from "@/shared/api/rest/client";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { BulkMutateGroups } from "@/entities/nodes/object/ui/object-table/toolbar/actions/groups/bulk-mutate-groups";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import { removeRelationships } from "@/entities/nodes/relationships/domain/remove-relationships/remove-relationships";
import type { NodeCore } from "@/entities/nodes/types";

export interface ToolbarRemoveFromGroupActionProps {
  selectedRows: Array<NodeCore>;
}

export function ToolbarRemoveFromGroupsAction({ selectedRows }: ToolbarRemoveFromGroupActionProps) {
  const { currentBranch } = useCurrentBranch();
  const { permission } = useObjectTableContext();
  const { isAllowed, message } = permission.update;

  if (!isAllowed) {
    return (
      <Tooltip message={message}>
        <Button variant="danger-outline" size="xs" isDisabledAndFocusable>
          Remove from groups
        </Button>
      </Tooltip>
    );
  }

  return (
    <DialogTrigger>
      <Button variant="danger-outline" size="xs">
        Remove from groups
      </Button>

      <Popover placement="top start" className="bg-white">
        <PopoverDialog>
          {({ close }) => (
            <BulkMutateGroups
              mutationFn={async (group) => {
                await removeRelationships({
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
              groupsQueryFilter={{ members__ids: selectedRows.map((row) => row.id) }}
            />
          )}
        </PopoverDialog>
      </Popover>
    </DialogTrigger>
  );
}
