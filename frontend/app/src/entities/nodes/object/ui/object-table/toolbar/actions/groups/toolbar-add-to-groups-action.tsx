import { DialogTrigger } from "react-aria-components";

import { Popover, PopoverDialog } from "@/shared/components/aria/popover";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { BulkMutateGroups } from "@/entities/nodes/object/ui/object-table/toolbar/actions/groups/bulk-mutate-groups";
import { ToolbarButtonWithTooltip } from "@/entities/nodes/object/ui/object-table/toolbar/toolbar-button";
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
      <ToolbarButtonWithTooltip isDisabled tooltipEnabled tooltipContent={message}>
        Add to groups
      </ToolbarButtonWithTooltip>
    );
  }

  return (
    <DialogTrigger>
      <ToolbarButtonWithTooltip>Add to groups</ToolbarButtonWithTooltip>

      <Popover placement="top start">
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
                onSuccess={close}
              />
            );
          }}
        </PopoverDialog>
      </Popover>
    </DialogTrigger>
  );
}
