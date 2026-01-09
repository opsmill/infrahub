import { TrashIcon } from "@heroicons/react/24/outline";
import { useState } from "react";
import { XIcon } from "lucide-react";

import ModalDelete from "@/shared/components/modals/modal-delete";
import { classNames } from "@/shared/utils/common";

import type { BranchListItem } from "@/entities/branches/domain/branch.mappers";
import { useDeleteBranchMutation } from "@/entities/branches/domain/delete-branch.mutation";
import { ToolbarButton } from "@/entities/nodes/object/ui/object-table/toolbar/toolbar-button";
import { ToolbarDivider } from "@/entities/nodes/object/ui/object-table/toolbar/toolbar-divider";

export interface BranchesToolbarProps {
  selectedBranches: Array<BranchListItem>;
  onClose: () => void;
}

export function BranchesToolbar({ selectedBranches, onClose }: BranchesToolbarProps) {
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const { mutateAsync: deleteBranch, isPending: isDeleting } = useDeleteBranchMutation();

  const deletableBranches = selectedBranches.filter((branch) => !branch.is_default);

  const handleDelete = async () => {
    for (const branch of deletableBranches) {
      await deleteBranch({ name: branch.name });
    }
    setShowDeleteModal(false);
    onClose();
  };

  return (
    <>
      <div
        role="dialog"
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
          <TrashIcon className="size-3.5" />
          Delete
        </ToolbarButton>
      </div>

      {showDeleteModal && (
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
          onCancel={() => setShowDeleteModal(false)}
          onDelete={handleDelete}
          open={showDeleteModal}
          setOpen={setShowDeleteModal}
          isLoading={isDeleting}
        />
      )}
    </>
  );
}
