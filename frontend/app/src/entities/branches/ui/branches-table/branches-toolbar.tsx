import { Icon } from "@iconify-icon/react";
import { XIcon } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "react-toastify";

import { constructPath, getCurrentQsp } from "@/shared/api/rest/fetch";
import { ModalDelete } from "@/shared/components/modals/modal-delete";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { QSP } from "@/shared/config/qsp";
import { classNames } from "@/shared/utils/common";

import type { BranchListItem } from "@/entities/branches/domain/branch.mappers";
import { useDeleteBranchesMutation } from "@/entities/branches/ui/queries/delete-branches.mutation";
import { ToolbarButton } from "@/entities/nodes/object/ui/object-table/toolbar/toolbar-button";
import { ToolbarDivider } from "@/entities/nodes/object/ui/object-table/toolbar/toolbar-divider";

export interface BranchesToolbarProps {
  selectedBranches: Array<BranchListItem>;
  onClose: () => void;
}

export function BranchesToolbar({ selectedBranches, onClose }: BranchesToolbarProps) {
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const { mutateAsync: deleteBranches, isPending: isDeleting } = useDeleteBranchesMutation();
  const navigate = useNavigate();

  const deletableBranches = selectedBranches.filter((branch) => !branch.is_default);

  const handleDelete = async () => {
    const branchNames = deletableBranches.map((branch) => branch.name);

    try {
      const result = await deleteBranches({ names: branchNames });

      if (result.failed.length > 0) {
        toast(
          <Alert
            type={ALERT_TYPES.ERROR}
            message={`Failed to delete ${result.failed.length === 1 ? "branch" : "branches"}: ${result.failed.join(", ")}`}
          />
        );
      }

      if (result.deleted.length > 0) {
        const queryStringParams = getCurrentQsp();
        const currentBranch = queryStringParams.get(QSP.BRANCH);
        const isCurrentBranchDeleted = currentBranch && result.deleted.includes(currentBranch);

        if (isCurrentBranchDeleted) {
          const path = constructPath("/branches", [{ name: QSP.BRANCH, exclude: true }]);
          navigate(path, { replace: true });
        }
      }
    } catch {
      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message={`Failed to delete ${branchNames.length === 1 ? "branch" : "branches"}: ${branchNames.join(", ")}`}
        />
      );
    }

    setShowDeleteModal(false);
    onClose();
  };

  return (
    <>
      <div
        role="toolbar"
        className={classNames(
          "fixed bottom-10 left-1/2 z-10 -translate-x-1/2 whitespace-nowrap",
          "text rounded-xl border border-neutral-300 px-1.5 text-sm shadow-lg backdrop-blur-lg",
          "fade-in-0 zoom-in-95 slide-in-from-bottom-1/2 animate-in",
          "flex items-center gap-1.5 outline-none"
        )}
        data-testid="branches-toolbar"
      >
        <ToolbarButton variant="ghost" onPress={onClose}>
          <span>{selectedBranches.length} selected</span>
          <XIcon className="size-3.5" />
        </ToolbarButton>

        <ToolbarDivider />

        <ToolbarButton
          variant="danger"
          isDisabled={deletableBranches.length === 0}
          onPress={() => setShowDeleteModal(true)}
        >
          <Icon icon="mdi:delete-outline" className="text-sm" />
          Delete
        </ToolbarButton>
      </div>

      <ModalDelete
        title="Delete"
        description={
          deletableBranches.length === 1 ? (
            <>
              Are you sure you want to remove the branch
              <br /> <b>`{deletableBranches[0].name}`</b>?
            </>
          ) : (
            <>
              Are you sure you want to remove {deletableBranches.length} branches?
              <br />
              <b>{deletableBranches.map((b) => b.name).join(", ")}</b>
            </>
          )
        }
        onDelete={handleDelete}
        isOpen={showDeleteModal}
        onOpenChange={setShowDeleteModal}
        isLoading={isDeleting}
      />
    </>
  );
}
