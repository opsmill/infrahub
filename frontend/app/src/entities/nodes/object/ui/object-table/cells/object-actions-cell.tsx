import { Icon } from "@iconify-icon/react";
import { useState } from "react";
import { Link } from "react-router";

import { queryClient } from "@/shared/api/rest/client";
import { Button } from "@/shared/components/buttons/button-primitive";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import { Tooltip } from "@/shared/components/ui/tooltip";

import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import { DeleteObjectModal } from "@/entities/nodes/object/ui/delete-object-modal";
import { StickyRightCell } from "@/entities/nodes/object/ui/object-table/cells/style";
import ObjectItemEditComponent from "@/entities/nodes/object-item-edit/object-item-edit-paginated";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import type { Permission } from "@/entities/permission/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

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

  if (!schema) {
    return <StickyRightCell isMuted />;
  }

  return (
    <>
      <StickyRightCell>
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
      </StickyRightCell>

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
              await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
              setShowEditForm(false);
            }}
            objectId={objectId}
            objectname={objectKind}
          />
        </SlideOver>
      )}

      <DeleteObjectModal
        objectKind={objectKind}
        objectId={objectId}
        objectLabel={objectLabel}
        isOpen={showDeleteModal}
        onOpenChange={setShowDeleteModal}
      />
    </>
  );
}
