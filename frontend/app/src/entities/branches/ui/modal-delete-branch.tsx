import { Icon } from "@iconify-icon/react";
import { useState } from "react";
import { Heading } from "react-aria-components";

import { Modal } from "@/shared/components/aria/modal";
import { Radio, RadioGroup } from "@/shared/components/aria/radio-group";
import { Col, Row } from "@/shared/components/container";
import { ModalDelete } from "@/shared/components/modals/modal-delete";
import { Button } from "@/shared/components/ui/button";
import { REPOSITORY_KIND } from "@/shared/config/constants";

import { useObjectsCount } from "@/entities/nodes/object/domain/get-objects-count.query";

export type DeleteBranchScope = "local" | "local-and-remote";

interface BranchRef {
  name: string;
  sync_with_git?: boolean | null;
}

interface ModalDeleteBranchProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  branches: BranchRef[];
  onDelete: (scope: DeleteBranchScope) => void | Promise<void>;
  isLoading?: boolean;
}

function buildDescription(branches: BranchRef[]) {
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
  const [scope, setScope] = useState<DeleteBranchScope>("local");
  const { data: repositoryCount } = useObjectsCount({
    objectKind: REPOSITORY_KIND,
  });

  const hasSyncedBranches = branches.some((b) => b.sync_with_git);
  const showScopeChoice = hasSyncedBranches && (repositoryCount ?? 0) > 0;
  const description = buildDescription(branches);

  if (!showScopeChoice) {
    return (
      <ModalDelete
        title="Delete"
        description={description}
        onDelete={() => onDelete("local")}
        isOpen={isOpen}
        onOpenChange={onOpenChange}
        isLoading={isLoading}
      />
    );
  }

  return (
    <Modal
      isDismissable={!isLoading}
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      className="w-full max-w-lg p-0"
      data-testid="modal-delete-branch"
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
          <Radio value="local">
            <div>
              <div className="font-medium text-sm">Local only</div>
              <div className="text-gray-500 text-xs">
                Remove the branch from Infrahub. The remote Git repository will not be affected.
              </div>
            </div>
          </Radio>
          <Radio value="local-and-remote">
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
        <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isLoading}>
          Cancel
        </Button>
        <Button
          variant="danger"
          onClick={() => onDelete(scope)}
          isLoading={isLoading}
          disabled={isLoading}
          data-testid="modal-delete-confirm"
        >
          Delete
        </Button>
      </Row>
    </Modal>
  );
}
