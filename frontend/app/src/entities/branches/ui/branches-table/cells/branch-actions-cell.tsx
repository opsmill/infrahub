import { Icon } from "@iconify-icon/react";
import { useState } from "react";
import { Link } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { Button } from "@/shared/components/buttons/button-primitive";
import { ModalDelete } from "@/shared/components/modals/modal-delete";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import { Tooltip } from "@/shared/components/ui/tooltip";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import type { BranchListItem } from "@/entities/branches/domain/branch.mappers";
import { useDeleteBranchMutation } from "@/entities/branches/domain/delete-branch.mutation";
import { StickyRightCell } from "@/entities/nodes/object/ui/object-table/cells/style";

export interface BranchActionsCellProps {
  branch: BranchListItem;
}

export function BranchActionsCell({ branch }: BranchActionsCellProps) {
  const { isAuthenticated } = useAuth();
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const { mutateAsync: deleteBranch, isPending: isDeleting } = useDeleteBranchMutation();

  const isDeleteAllowed = isAuthenticated && !branch.is_default;

  return (
    <>
      <StickyRightCell className="h-auto min-h-14">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              size="square"
              variant="ghost"
              className="size-6"
              data-testid={`branch-actions-cell-${branch.name}`}
            >
              <Icon icon={"mdi:dots-vertical"} className="text-gray-500" />
            </Button>
          </DropdownMenuTrigger>

          <DropdownMenuContent align="end">
            <DropdownMenuItem asChild>
              <Link to={constructPath(`/branches/${branch.name}`)}>
                <Icon icon="mdi:arrow-expand" className="text-base" />
                View details
              </Link>
            </DropdownMenuItem>

            <Tooltip
              enabled={!isDeleteAllowed}
              content={branch.is_default ? "Cannot delete the default branch" : "Login required"}
              side="left"
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

      <ModalDelete
        title="Delete"
        description={
          <>
            Are you sure you want to remove the branch
            <br /> <b>`{branch.name}`</b>?
          </>
        }
        onDelete={async () => {
          await deleteBranch({ name: branch.name });
          setShowDeleteModal(false);
        }}
        isOpen={showDeleteModal}
        onOpenChange={setShowDeleteModal}
        isLoading={isDeleting}
      />
    </>
  );
}
