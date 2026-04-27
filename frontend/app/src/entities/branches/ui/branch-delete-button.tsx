import { Icon } from "@iconify-icon/react";
import { useState } from "react";

import { Button } from "@/shared/components/aria/button";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import type { BranchDetail } from "@/entities/branches/domain/branch.mappers";
import { useNavigateAfterBranchRemoval } from "@/entities/branches/ui/hooks/use-navigate-after-branch-removal";
import { DELETE_BRANCH_SCOPE, ModalDeleteBranch } from "@/entities/branches/ui/modal-delete-branch";
import { useDeleteBranchMutation } from "@/entities/branches/ui/queries/delete-branch.mutation";

type BranchDeleteButtonProps = {
  branch: BranchDetail;
};

export const BranchDeleteButton = ({ branch }: BranchDeleteButtonProps) => {
  const { isAuthenticated } = useAuth();
  const [displayModal, setDisplayModal] = useState(false);
  const { navigateToPage } = useNavigateAfterBranchRemoval();
  const { mutateAsync: deleteBranch, isPending: isDeleting } = useDeleteBranchMutation();

  const isDisabled = !isAuthenticated || !!branch.is_default || isDeleting;

  return (
    <>
      <Button isDisabled={isDisabled} onPress={() => setDisplayModal(true)} variant="danger">
        Delete
        <Icon icon="mdi:delete-outline" className="text-base" aria-hidden="true" />
      </Button>

      <ModalDeleteBranch
        branches={[branch]}
        onDelete={async (scope) => {
          navigateToPage("/branches", branch.name);
          await deleteBranch({
            name: branch.name,
            deleteFromGit: scope === DELETE_BRANCH_SCOPE.LOCAL_AND_REMOTE,
          });
        }}
        isOpen={displayModal}
        onOpenChange={setDisplayModal}
        isLoading={isDeleting}
      />
    </>
  );
};
