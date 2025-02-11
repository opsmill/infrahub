import {
  DeleteObjectModal,
  DeleteObjectModalProps,
} from "@/entities/nodes/object/ui/delete-object-modal";
import { TableCell } from "@/entities/nodes/object/ui/objects-table/cells/table-cell";
import { getObjectDetailsUrl2 } from "@/entities/nodes/utils";
import { Permission } from "@/entities/permission/types";
import { Button } from "@/shared/components/buttons/button-primitive";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { Icon } from "@iconify-icon/react";
import { useState } from "react";
import { Link } from "react-router";

export interface ActionsCellProps extends Omit<DeleteObjectModalProps, "open" | "setOpen"> {
  permission: Permission;
}

export function ActionsCell({ objectKind, objectId, objectLabel, permission }: ActionsCellProps) {
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const isDeleteAllowed = permission.delete.isAllowed;

  return (
    <>
      <TableCell className="sticky right-0 border-l size-10 items-center justify-center bg-white -ml-px">
        <div className="absolute -left-4 top-0 bottom-0 w-4 bg-gradient-to-r from-transparent to-gray-300/30 pointer-events-none" />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              size="square"
              variant="ghost"
              className="size-6"
              data-testid={`actions-cell-${objectLabel}`}
            >
              <Icon icon={"mdi:dots-vertical"} className="text-gray-500" />
            </Button>
          </DropdownMenuTrigger>

          <DropdownMenuContent align="end">
            <DropdownMenuItem asChild>
              <Link to={getObjectDetailsUrl2(objectKind, objectId)}>
                <Icon icon="mdi:arrow-expand" className="text-base" />
                View details
              </Link>
            </DropdownMenuItem>

            <Tooltip enabled={!isDeleteAllowed} content={permission.delete.message} side="left">
              <div>
                <DropdownMenuItem
                  disabled={!isDeleteAllowed}
                  onClick={() => isDeleteAllowed && setShowDeleteModal(true)}
                >
                  <Icon icon="mdi:delete-outline" className="text-base" />
                  Delete
                </DropdownMenuItem>
              </div>
            </Tooltip>
          </DropdownMenuContent>
        </DropdownMenu>
      </TableCell>

      {showDeleteModal && (
        <DeleteObjectModal
          objectKind={objectKind}
          objectId={objectId}
          objectLabel={objectLabel}
          open={true}
          setOpen={() => setShowDeleteModal(false)}
        />
      )}
    </>
  );
}
