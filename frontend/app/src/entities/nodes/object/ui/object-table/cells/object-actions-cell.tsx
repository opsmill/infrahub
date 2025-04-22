import ObjectItemEditComponent from "@/entities/nodes/object-item-edit/object-item-edit-paginated";
import { DeleteObjectModal } from "@/entities/nodes/object/ui/delete-object-modal";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { Permission } from "@/entities/permission/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { queryClient } from "@/shared/api/rest/client";
import { Button } from "@/shared/components/buttons/button-primitive";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { TableCell } from "@/shared/components/table/table-cell";
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

export interface ActionsCellProps {
  permission: Permission;
  objectId: string;
  objectKind: string;
  objectLabel: string;
}

export function ObjectActionsCell({
  objectKind,
  objectId,
  objectLabel,
  permission,
}: ActionsCellProps) {
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showEditForm, setShowEditForm] = useState(false);
  const { schema } = useSchema(objectKind);
  const isEditAllowed = permission.update.isAllowed;
  const isDeleteAllowed = permission.delete.isAllowed;

  if (!schema) return <ErrorScreen message={`Schema not found for ${objectKind}`} />;

  return (
    <>
      <TableCell className="sticky right-0 border-l size-10 items-center justify-center bg-white -ml-px">
        <div className="absolute -left-4 top-0 bottom-0 w-4 bg-linear-to-r from-transparent to-gray-300/30 pointer-events-none" />
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
              <Link to={getObjectDetailsUrl(objectKind, objectId)}>
                <Icon icon="mdi:arrow-expand" className="text-base" />
                View details
              </Link>
            </DropdownMenuItem>

            <Tooltip enabled={!isEditAllowed} content={permission.update.message} side="left">
              <div>
                <DropdownMenuItem
                  disabled={!isEditAllowed}
                  onClick={() => isEditAllowed && setShowEditForm(true)}
                >
                  <Icon icon="mdi:edit-outline" className="text-base" />
                  Edit
                </DropdownMenuItem>
              </div>
            </Tooltip>

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

      {showEditForm && (
        <SlideOver
          title={
            <SlideOverTitle
              schema={schema}
              currentObjectLabel={objectLabel}
              title={`Edit ${objectLabel}`}
            />
          }
          open={true}
          setOpen={() => setShowEditForm(false)}
        >
          <ObjectItemEditComponent
            closeDrawer={() => setShowEditForm(false)}
            onUpdateComplete={async () => {
              await queryClient.invalidateQueries({
                predicate: (query) => query.queryKey.includes("objects"),
              });
            }}
            objectid={objectId}
            objectname={objectKind}
          />
        </SlideOver>
      )}

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
