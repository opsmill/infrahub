import {
  DeleteObjectModal,
  DeleteObjectModalProps,
} from "@/entities/nodes/object/ui/delete-object-modal";
import { TableCell } from "@/entities/nodes/object/ui/objects-table/cells/table-cell";
import { getObjectDetailsUrl2 } from "@/entities/nodes/utils";
import { Button } from "@/shared/components/buttons/button-primitive";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import { Icon } from "@iconify-icon/react";
import { useState } from "react";
import { Link } from "react-router-dom";

export interface ActionsCellProps extends Omit<DeleteObjectModalProps, "open" | "setOpen"> {}

export function ActionsCell({ objectKind, objectId, objectLabel }: ActionsCellProps) {
  const [showDeleteModal, setShowDeleteModal] = useState(false);

  return (
    <>
      <TableCell className="sticky right-0 border-l size-10 items-center justify-center  -ml-px">
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

            <DropdownMenuItem onClick={() => setShowDeleteModal(true)}>
              <Icon icon="mdi:delete-outline" className="text-base" />
              Delete
            </DropdownMenuItem>
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
