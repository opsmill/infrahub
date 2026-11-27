import { Button, Popover, PopoverDialog, Tooltip } from "@infrahub/ui";
import { DialogTrigger } from "react-aria-components";

import { queryClient } from "@/shared/api/rest/client";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { GROUP_MEMBERS_RELATIONSHIP } from "@/entities/groups/domain/model/group";
import type { NodeCore } from "@/entities/nodes/object/domain/model/node";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import {
  BulkMutateGroups,
  type BulkMutateGroupsProps,
} from "@/entities/nodes/object/ui/object-table/toolbar/actions/groups/bulk-mutate-groups";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import type { RemoveRelationshipsParams } from "@/entities/nodes/relationships/domain/use-cases/remove-relationships";

export interface ToolbarGroupsActionProps {
  selectedRows: Array<NodeCore>;
  label: string;
  variant: "outline" | "danger-outline";
  mutateMembers: (params: RemoveRelationshipsParams) => Promise<void>;
  groupsQueryFilter: BulkMutateGroupsProps["groupsQueryFilter"];
}

export function ToolbarGroupsAction({
  selectedRows,
  label,
  variant,
  mutateMembers,
  groupsQueryFilter,
}: ToolbarGroupsActionProps) {
  const { currentBranch } = useCurrentBranch();
  const { permission } = useObjectTableContext();
  const { isAllowed, message } = permission.update;

  if (!isAllowed) {
    return (
      <Tooltip message={message}>
        <Button variant={variant} size="xs" isDisabledAndFocusable>
          {label}
        </Button>
      </Tooltip>
    );
  }

  return (
    <DialogTrigger>
      <Button variant={variant} size="xs">
        {label}
      </Button>

      <Popover placement="top start">
        <PopoverDialog>
          {({ close }) => (
            <BulkMutateGroups
              mutationFn={async (group) => {
                await mutateMembers({
                  objectId: group.id,
                  relationshipName: GROUP_MEMBERS_RELATIONSHIP,
                  relationshipIds: selectedRows.map((row) => row.id),
                  branchName: currentBranch.name,
                });
              }}
              onSuccess={async () => {
                await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
              }}
              onClose={close}
              groupsQueryFilter={groupsQueryFilter}
            />
          )}
        </PopoverDialog>
      </Popover>
    </DialogTrigger>
  );
}
