import { Icon } from "@iconify-icon/react";
import { useState } from "react";
import { Heading } from "react-aria-components";

import { Button } from "@/shared/components/aria/button";
import { Modal } from "@/shared/components/aria/modal";
import { Radio, RadioGroup } from "@/shared/components/aria/radio-group";
import { Col, Row } from "@/shared/components/container";
import { ModalDelete } from "@/shared/components/modals/modal-delete";
import { REPOSITORY_KIND } from "@/shared/config/constants";
import { classNames } from "@/shared/utils/common";

import { useObjectsCount } from "@/entities/nodes/object/ui/queries/get-objects-count.query";

export const DELETE_BRANCH_SCOPE = {
  LOCAL: "local",
  LOCAL_AND_REMOTE: "local-and-remote",
} as const;

export type DeleteBranchScope = (typeof DELETE_BRANCH_SCOPE)[keyof typeof DELETE_BRANCH_SCOPE];

interface BranchSummary {
  name: string;
  sync_with_git?: boolean | null;
}

interface ModalDeleteBranchProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  branches: BranchSummary[];
  onDelete: (scope: DeleteBranchScope) => void | Promise<void>;
  isLoading?: boolean;
}

function buildDescription(branches: BranchSummary[]) {
  if (branches.length === 1) {
    return (
      <>
        Are you sure you want to remove the branch
        <br /> <b>`{branches[0]?.name}`</b>?
      </>
    );
  }

  return (
    <>
      Are you sure you want to remove {branches.length} branches?
      <br />
      <b>{branches.map((b) => b.name).join(", ")}</b>
    </>
  );
}

export function ModalDeleteBranch({
  isOpen,
  onOpenChange,
  branches,
  onDelete,
  isLoading,
}: ModalDeleteBranchProps) {
  const [scope, setScope] = useState<DeleteBranchScope>(DELETE_BRANCH_SCOPE.LOCAL);

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      setScope(DELETE_BRANCH_SCOPE.LOCAL);
    }
    onOpenChange(open);
  };

  const { data: repositoryCount, isLoading: isLoadingRepoCount } = useObjectsCount({
    objectKind: REPOSITORY_KIND,
  });

  const hasSyncedBranches = branches.some((b) => b.sync_with_git);
  const showScopeChoice = hasSyncedBranches && repositoryCount !== undefined && repositoryCount > 0;
  const description = buildDescription(branches);

  if (!showScopeChoice && !(hasSyncedBranches && isLoadingRepoCount)) {
    return (
      <ModalDelete
        title="Delete"
        description={description}
        onDelete={() => onDelete(DELETE_BRANCH_SCOPE.LOCAL)}
        isOpen={isOpen}
        onOpenChange={handleOpenChange}
        isLoading={isLoading}
      />
    );
  }

  return (
    <Modal
      isDismissable={!isLoading}
      isOpen={isOpen}
      onOpenChange={handleOpenChange}
      className="w-full max-w-lg p-0"
      data-testid="modal-delete"
    >
      <Col className="gap-4 p-3">
        <Heading slot="title" className="flex items-center gap-2 p-1 font-semibold">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-red-100">
            <Icon icon="mdi:warning-outline" className="text-red-600" />
          </div>
          Delete
        </Heading>

        <p className="px-8 text-gray-500 text-sm">{description}</p>

        <RadioGroup
          value={scope}
          onChange={(value) => setScope(value as DeleteBranchScope)}
          className="px-8"
          aria-label="Deletion scope"
        >
          <Radio
            value={DELETE_BRANCH_SCOPE.LOCAL}
            className={classNames(
              "rounded-lg border p-3",
              scope === DELETE_BRANCH_SCOPE.LOCAL ? "border-custom-blue-600" : "border-gray-200"
            )}
          >
            <div>
              <div className="font-medium text-sm">Local only</div>
              <div className="text-gray-500 text-xs">
                Remove the branch from Infrahub. The remote Git repository will not be affected.
              </div>
            </div>
          </Radio>
          <Radio
            value={DELETE_BRANCH_SCOPE.LOCAL_AND_REMOTE}
            className={classNames(
              "rounded-lg border p-3",
              scope === DELETE_BRANCH_SCOPE.LOCAL_AND_REMOTE
                ? "border-custom-blue-600"
                : "border-gray-200"
            )}
          >
            <div>
              <div className="font-medium text-sm">Local and remote</div>
              <div className="text-gray-500 text-xs">
                Remove the branch from Infrahub and delete it from the remote Git repository.
              </div>
            </div>
          </Radio>
        </RadioGroup>
      </Col>

      <Row className="justify-end bg-gray-50 p-3">
        <Button variant="outline" onPress={() => handleOpenChange(false)} isDisabled={isLoading}>
          Cancel
        </Button>
        <Button
          variant="danger"
          onPress={() => onDelete(scope)}
          isPending={isLoading || isLoadingRepoCount}
          isDisabled={isLoading || isLoadingRepoCount}
          data-testid="modal-delete-confirm"
        >
          Delete
        </Button>
      </Row>
    </Modal>
  );
}
