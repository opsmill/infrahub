import { Icon } from "@iconify-icon/react";
import { Button } from "@infrahub/ui";
import { XIcon } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router";
import { toast } from "react-toastify";

import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { QSP } from "@/shared/config/qsp";
import { classNames } from "@/shared/utils/common";

import type { BranchListItem } from "@/entities/branches/domain/branch.mappers";
import { useNavigateAfterBranchRemoval } from "@/entities/branches/ui/hooks/use-navigate-after-branch-removal";
import { DELETE_BRANCH_SCOPE, ModalDeleteBranch } from "@/entities/branches/ui/modal-delete-branch";
import { useDeleteBranchesMutation } from "@/entities/branches/ui/queries/delete-branches.mutation";
import { ToolbarDivider } from "@/entities/nodes/object/ui/object-table/toolbar/toolbar-divider";

export interface BranchesToolbarProps {
  selectedBranches: Array<BranchListItem>;
  onClose: () => void;
}

export function BranchesToolbar({ selectedBranches, onClose }: BranchesToolbarProps) {
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [searchParams] = useSearchParams();
  const { mutateAsync: deleteBranches, isPending: isDeleting } = useDeleteBranchesMutation();
  const { clearBranchIfCurrent } = useNavigateAfterBranchRemoval();

  const deletableBranches = selectedBranches.filter((branch) => !branch.is_default);

  const handleDelete = async (deleteFromGit: boolean) => {
    const branchNames = deletableBranches.map((branch) => branch.name);

    const currentBranch = searchParams.get(QSP.BRANCH);
    if (currentBranch && branchNames.includes(currentBranch)) {
      clearBranchIfCurrent(currentBranch);
    }

    try {
      const result = await deleteBranches({ names: branchNames, deleteFromGit });

      if (result.failed.length > 0) {
        toast(
          <Alert
            type={ALERT_TYPES.ERROR}
            message={`Failed to delete ${result.failed.length === 1 ? "branch" : "branches"}: ${result.failed.join(", ")}`}
          />
        );
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
        <Button variant="ghost" size="xs" onPress={onClose}>
          <span>{selectedBranches.length} selected</span>
          <XIcon className="size-3.5" />
        </Button>

        <ToolbarDivider />

        <Button
          variant="danger-outline"
          size="xs"
          isDisabled={deletableBranches.length === 0}
          onPress={() => setShowDeleteModal(true)}
        >
          <Icon icon="mdi:delete-outline" className="text-sm" />
          Delete
        </Button>
      </div>

      <ModalDeleteBranch
        branches={deletableBranches}
        onDelete={async (scope) => {
          await handleDelete(scope === DELETE_BRANCH_SCOPE.LOCAL_AND_REMOTE);
        }}
        isOpen={showDeleteModal}
        onOpenChange={setShowDeleteModal}
        isLoading={isDeleting}
      />
    </>
  );
}
