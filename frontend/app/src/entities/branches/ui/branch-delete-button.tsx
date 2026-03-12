import { Icon } from "@iconify-icon/react";
import { useState } from "react";
import { useNavigate } from "react-router";

import { constructPath, getCurrentQsp } from "@/shared/api/rest/fetch";
import { Button } from "@/shared/components/ui/button";
import { QSP } from "@/shared/config/qsp";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import type { BranchDetail } from "@/entities/branches/domain/branch.mappers";
import { ModalDeleteBranch } from "@/entities/branches/ui/modal-delete-branch";
import { useDeleteBranchMutation } from "@/entities/branches/ui/queries/delete-branch.mutation";

type BranchDeleteButtonProps = {
  branch: BranchDetail;
};

export const BranchDeleteButton = ({ branch }: BranchDeleteButtonProps) => {
  const { isAuthenticated } = useAuth();
  const [displayModal, setDisplayModal] = useState(false);
  const navigate = useNavigate();
  const { mutateAsync: deleteBranch, isPending: isDeleting } = useDeleteBranchMutation();

  const isDisabled = !isAuthenticated || !!branch.is_default || isDeleting;

  return (
    <>
      <Button disabled={isDisabled} onClick={() => setDisplayModal(true)} variant="danger">
        Delete
        <Icon icon="mdi:delete-outline" className="ml-2 text-base" aria-hidden="true" />
      </Button>

      <ModalDeleteBranch
        branches={[branch]}
        onDelete={async (_scope) => {
          // TODO: pass _scope to mutation once backend supports deleteRemote parameter
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
