import { DialogTrigger } from "react-aria-components";

import { Popover, PopoverDialog } from "@/shared/components/aria/popover";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { BulkMutateGroups } from "@/entities/nodes/object/ui/object-table/toolbar/actions/groups/bulk-mutate-groups";
import { ToolbarButtonWithTooltip } from "@/entities/nodes/object/ui/object-table/toolbar/toolbar-button";
import { removeRelationships } from "@/entities/nodes/relationships/domain/remove-relationships/remove-relationships";
import type { NodeCore } from "@/entities/nodes/types";

export interface ToolBarRemoveFromGroupActionProps {
  selectedRows: Array<NodeCore>;
}

export function ToolBarRemoveFromGroupsAction({ selectedRows }: ToolBarRemoveFromGroupActionProps) {
  const { currentBranch } = useCurrentBranch();
  const { permission } = useObjectTableContext();
  const { isAllowed, message } = permission.update;

  if (!isAllowed) {
    return (
      <ToolbarButtonWithTooltip variant="danger" isDisabled tooltipEnabled tooltipContent={message}>
        Remove from groups
      </ToolbarButtonWithTooltip>
    );
  }

  return (
    <DialogTrigger>
      <ToolbarButtonWithTooltip variant="danger">Remove from groups</ToolbarButtonWithTooltip>

      <Popover placement="top start">
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
              onSuccess={close}
              groupsQueryFilter={{ members__ids: selectedRows.map((row) => row.id) }}
            />
          )}
        </PopoverDialog>
      </Popover>
    </DialogTrigger>
  );
}
