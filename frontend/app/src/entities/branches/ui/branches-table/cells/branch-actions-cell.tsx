import { Icon } from "@iconify-icon/react";
import { Button, Tooltip } from "@infrahub/ui";
import { useState } from "react";
import { Link } from "react-router";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";

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
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              size="sm"
              shape="square"
              variant="ghost"
              data-testid={`branch-actions-cell-${branch.name}`}
            >
              <Icon icon={"mdi:dots-vertical"} className="text-gray-500" />
            </Button>
          </DropdownMenuTrigger>

          <DropdownMenuContent align="end">
            <DropdownMenuItem asChild>
              <Link to={getBranchDetailsUrl(branch.name)}>
                <Icon icon="mdi:arrow-expand" className="text-base" />
                View details
              </Link>
            </DropdownMenuItem>

            <Tooltip
              message={
                isDeleteAllowed
                  ? undefined
                  : branch.is_default
                    ? "Cannot delete the default branch"
                    : "Login required"
              }
              placement="left"
              nonInteractiveTrigger
            >
              <div>
                <DropdownMenuItem
                  disabled={!isDeleteAllowed}
                  onClick={() => isDeleteAllowed && setShowDeleteModal(true)}
                >
                  <Icon icon="mdi:delete-outline" className="text-base" />
                  Delete
                </DropdownMenuItem>
              </div>
            </Tooltip>
          </DropdownMenuContent>
        </DropdownMenu>
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
