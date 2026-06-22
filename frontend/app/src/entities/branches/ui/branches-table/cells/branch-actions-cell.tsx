import { Icon } from "@iconify-icon/react";
import { Button, Menu, MenuItem, MenuTrigger, Popover } from "@infrahub/ui";
import { useState } from "react";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import type { BranchListItem } from "@/entities/branches/domain/branch.mappers";
import { useNavigateAfterBranchRemoval } from "@/entities/branches/ui/hooks/use-navigate-after-branch-removal";
import { DELETE_BRANCH_SCOPE, ModalDeleteBranch } from "@/entities/branches/ui/modal-delete-branch";
import { useDeleteBranchMutation } from "@/entities/branches/ui/queries/delete-branch.mutation";
import { getBranchDetailsUrl } from "@/entities/branches/utils";
import { StickyRightCell } from "@/entities/nodes/object/ui/object-table/cells/style";

export interface BranchActionsCellProps {
  branch: BranchListItem;
}

export function BranchActionsCell({ branch }: BranchActionsCellProps) {
  const { isAuthenticated } = useAuth();
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const { clearBranchIfCurrent } = useNavigateAfterBranchRemoval();
  const { mutateAsync: deleteBranch, isPending: isDeleting } = useDeleteBranchMutation();

  const isDeleteAllowed = isAuthenticated && !branch.is_default;

  return (
    <>
      <StickyRightCell className="h-auto min-h-14">
        <MenuTrigger>
          <Button
            size="sm"
            shape="square"
            variant="ghost"
            data-testid={`branch-actions-cell-${branch.name}`}
          >
            <Icon icon={"mdi:dots-vertical"} className="text-gray-500" />
          </Button>

          <Popover placement="bottom end">
            <Menu aria-label="Branch actions">
              <MenuItem href={getBranchDetailsUrl(branch.name)}>
                <Icon icon="mdi:arrow-expand" className="text-base" />
                View details
              </MenuItem>

              <MenuItem
                isDisabled={!isDeleteAllowed}
                tooltip={branch.is_default ? "Cannot delete the default branch" : "Login required"}
                onAction={() => setShowDeleteModal(true)}
              >
                <Icon icon="mdi:delete-outline" className="text-base" />
                Delete
              </MenuItem>
            </Menu>
          </Popover>
        </MenuTrigger>
      </StickyRightCell>

      <ModalDeleteBranch
        branches={[branch]}
        onDelete={async (scope) => {
          clearBranchIfCurrent(branch.name);
          await deleteBranch({
            name: branch.name,
            deleteFromGit: scope === DELETE_BRANCH_SCOPE.LOCAL_AND_REMOTE,
          });
          setShowDeleteModal(false);
        }}
        isOpen={showDeleteModal}
        onOpenChange={setShowDeleteModal}
        isLoading={isDeleting}
      />
    </>
  );
}
