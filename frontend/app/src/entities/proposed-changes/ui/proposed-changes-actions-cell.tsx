import { Icon } from "@iconify-icon/react";
import { Button, Menu, MenuItem, MenuTrigger, Popover } from "@infrahub/ui";
import { Trash2Icon } from "lucide-react";
import { useState } from "react";

import { DeleteObjectModal } from "@/entities/nodes/object/ui/delete-object-modal";
import type { Permission } from "@/entities/permission/types";
import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/constants";

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
      <MenuTrigger>
        <Button
          size="sm"
          shape="square"
          variant="ghost"
          data-testid={`actions-row-button-${objectLabel}`}
          aria-label="Actions"
        >
          <Icon icon={"mdi:dots-vertical"} className="text-gray-500" />
        </Button>

        <Popover placement="bottom end">
          <Menu aria-label="Actions">
            <MenuItem
              isDisabled={!isDeleteAllowed}
              tooltip={permission.delete.message}
              className="text-red-500"
              onAction={() => setShowDeleteModal(true)}
              data-testid={"delete-row-button"}
            >
              <Trash2Icon />
              <span>Delete</span>
            </MenuItem>
          </Menu>
        </Popover>
      </MenuTrigger>

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
