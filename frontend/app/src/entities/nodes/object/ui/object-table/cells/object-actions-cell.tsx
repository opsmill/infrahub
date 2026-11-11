import { Button, Menu, MenuItem, MenuTrigger, Popover, Sheet } from "@infrahub/ui";
import { EllipsisVerticalIcon, Maximize2Icon, PencilLineIcon, Trash2Icon } from "lucide-react";
import { useState } from "react";

import { queryClient } from "@/shared/api/rest/client";
import { SlideOverTitle } from "@/shared/components/display/slide-over";

import { DeleteObjectModal } from "@/entities/nodes/object/ui/delete-object-modal";
import ObjectEdit from "@/entities/nodes/object/ui/object-edit/object-item-edit-paginated";
import { StickyRightCell } from "@/entities/nodes/object/ui/object-table/cells/style";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import type { Permission } from "@/entities/permission/domain/model/permission";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export interface ActionsCellProps {
  permission: Permission;
  objectId: string;
  objectKind: string;
  objectLabel: string;
  extraRelationshipNames?: string[];
}

export function ObjectActionsCell({
  objectKind,
  objectId,
  objectLabel,
  permission,
  extraRelationshipNames,
}: ActionsCellProps) {
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showEditForm, setShowEditForm] = useState(false);
  const { schema } = useSchema(objectKind);

  const { isAllowed: isEditAllowed, message: editTooltipMessage } = permission.update;
  const { isAllowed: isDeleteAllowed, message: deleteTooltipMessage } = permission.delete;

  if (!schema) {
    return <StickyRightCell isMuted />;
  }

  return (
    <>
      <StickyRightCell>
        <MenuTrigger>
          <Button
            size="sm"
            shape="square"
            variant="ghost"
            data-testid={`actions-cell-${objectLabel}`}
          >
            <EllipsisVerticalIcon className="text-foreground-muted" />
          </Button>

          <Popover placement="bottom end">
            <Menu aria-label="Object actions">
              <MenuItem href={getObjectDetailsUrl(objectKind, objectId)}>
                <Maximize2Icon />
                <span>View details</span>
              </MenuItem>

              <MenuItem
                isDisabled={!isEditAllowed}
                tooltip={editTooltipMessage}
                onAction={() => setShowEditForm(true)}
              >
                <PencilLineIcon />
                <span>Edit</span>
              </MenuItem>

              <MenuItem
                isDisabled={!isDeleteAllowed}
                tooltip={deleteTooltipMessage}
                className="text-danger"
                onAction={() => setShowDeleteModal(true)}
              >
                <Trash2Icon />
                <span>Delete</span>
              </MenuItem>
            </Menu>
          </Popover>
        </MenuTrigger>
      </StickyRightCell>

      <Sheet isOpen={showEditForm} onOpenChange={() => setShowEditForm(false)}>
        <SlideOverTitle
          schema={schema}
          currentObjectLabel={objectLabel}
          title={`Edit ${objectLabel}`}
        />
        <ObjectEdit
          closeDrawer={() => setShowEditForm(false)}
          onUpdateComplete={async () => {
            await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
            setShowEditForm(false);
          }}
          objectId={objectId}
          objectKind={objectKind}
          extraRelationshipNames={extraRelationshipNames}
        />
      </Sheet>

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
