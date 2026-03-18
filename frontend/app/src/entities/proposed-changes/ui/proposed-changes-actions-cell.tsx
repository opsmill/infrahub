import { Icon } from "@iconify-icon/react";
import { useState } from "react";

import { Button } from "@/shared/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import { Tooltip } from "@/shared/components/ui/tooltip";

import { DeleteObjectModal } from "@/entities/nodes/object/ui/delete-object-modal";
import type { Permission } from "@/entities/permission/types";

import { PROPOSED_CHANGE_OBJECT } from "../constants";

export interface ActionsCellProps {
  permission: Permission;
  objectId: string;
  objectLabel: string;
}

export function ProposedChangesActionCell({ objectId, objectLabel, permission }: ActionsCellProps) {
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const isDeleteAllowed = permission.delete.isAllowed;

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            size="square"
            variant="ghost"
            className="size-6"
            data-testid={`actions-row-button-${objectLabel}`}
          >
            <Icon icon={"mdi:dots-vertical"} className="text-gray-500" />
          </Button>
        </DropdownMenuTrigger>

        <DropdownMenuContent align="end">
          <Tooltip enabled={!isDeleteAllowed} content={permission.delete.message} side="left">
            <div>
              <DropdownMenuItem
                disabled={!isDeleteAllowed}
                onClick={() => isDeleteAllowed && setShowDeleteModal(true)}
                data-testid={"delete-row-button"}
              >
                <Icon icon="mdi:delete-outline" className="text-base" />
                Delete
              </DropdownMenuItem>
            </div>
          </Tooltip>
        </DropdownMenuContent>
      </DropdownMenu>

      <DeleteObjectModal
        objectKind={PROPOSED_CHANGE_OBJECT}
        objectId={objectId}
        objectLabel={objectLabel}
        isOpen={showDeleteModal}
        onOpenChange={setShowDeleteModal}
        toastMessage={`Proposed changes ${objectLabel} deleted`}
      />
    </>
  );
}
