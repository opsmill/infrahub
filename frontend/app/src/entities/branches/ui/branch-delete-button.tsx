import { Icon } from "@iconify-icon/react";
import { useState } from "react";
import { useNavigate } from "react-router";

import { constructPath, getCurrentQsp } from "@/shared/api/rest/fetch";
import { ModalDelete } from "@/shared/components/modals/modal-delete";
import { Button } from "@/shared/components/ui/button";
import { QSP } from "@/shared/config/qsp";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { BRANCH_STATUS } from "@/entities/branches/constants";
import type { BranchDetail } from "@/entities/branches/domain/branch.mappers";
import { useDeleteBranchMutation } from "@/entities/branches/domain/delete-branch.mutation";

type BranchDeleteButtonProps = {
  branch: BranchDetail;
};

export const BranchDeleteButton = ({ branch }: BranchDeleteButtonProps) => {
  const { isAuthenticated } = useAuth();
  const [displayModal, setDisplayModal] = useState(false);
  const navigate = useNavigate();
  const { mutateAsync: deleteBranch, isPending: isDeleting } = useDeleteBranchMutation();

  const isMerged = branch.status === BRANCH_STATUS.MERGED;
  const isDisabled = !isAuthenticated || !!branch.is_default || isMerged || isDeleting;

  return (
    <>
      <Button disabled={isDisabled} onClick={() => setDisplayModal(true)} variant={"danger"}>
        Delete
        <Icon icon="mdi:delete-outline" className="ml-2 text-base" aria-hidden="true" />
      </Button>

      <ModalDelete
        title="Delete"
        description={
          <>
            Are you sure you want to remove the branch <b>`{branch.name}`</b>?
          </>
        }
        onDelete={async () => {
          await deleteBranch({ name: branch.name });

          const queryStringParams = getCurrentQsp();
          const isDeletedBranchSelected = queryStringParams.get(QSP.BRANCH) === branch.name;

          const path = isDeletedBranchSelected
            ? constructPath("/branches", [{ name: QSP.BRANCH, exclude: true }])
            : constructPath("/branches");

          navigate(path);
        }}
        isOpen={displayModal}
        onOpenChange={setDisplayModal}
        isLoading={isDeleting}
      />
    </>
  );
};
