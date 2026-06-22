import { Icon } from "@iconify-icon/react";
import { Popover as AriaPopover, Button, Menu, MenuItem, MenuTrigger, Sheet } from "@infrahub/ui";
import { useState } from "react";

import { queryClient } from "@/shared/api/rest/client";
import { SlideOverTitle } from "@/shared/components/display/slide-over";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { TableCell } from "@/shared/components/table/table-cell";
import { Popover, PopoverAnchor, PopoverContent } from "@/shared/components/ui/popover";

import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import ObjectItemEditComponent from "@/entities/nodes/object-item-edit/object-item-edit-paginated";
import { DissociateRelationshipsModal } from "@/entities/nodes/relationships/ui/dissociate-relationships-modal";
import { RelationshipProperties } from "@/entities/nodes/relationships/ui/relationship-properties";
import { canDissociateRelationship } from "@/entities/nodes/relationships/utils/can-dissociate-relationship";
import type { Permission } from "@/entities/permission/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export interface ActionsCellProps {
  parentId: string;
  parentKind: string;
  permission: Permission;
  relationshipId: string;
  relationshipKind: string;
  relationshipLabel: string;
  relationshipName: string;
  relationshipsCount: number;
}

export function RelationshipActionsCell({
  parentId,
  parentKind,
  permission,
  relationshipId,
  relationshipLabel,
  relationshipKind,
  relationshipName,
  relationshipsCount,
}: ActionsCellProps) {
  const [showPropertiesModal, setShowPropertiesModal] = useState(false);
  const [showEditForm, setShowEditForm] = useState(false);
  const [showDissociateModal, setShowDissociateModal] = useState(false);

  const { schema: parentSchema } = useSchema(parentKind);

  if (!parentSchema) {
    return <ErrorScreen message={`Schema not found for ${relationshipKind}`} />;
  }

  const { isAllowed: isEditAllowed, message: editTooltipMessage } = permission.update;
  const isDissociateAllowed = canDissociateRelationship({
    parentSchema,
    relationshipName,
    relationshipsCount,
  });

  return (
    <Popover open={showPropertiesModal} onOpenChange={setShowPropertiesModal}>
      <TableCell className="sticky right-0 -ml-px size-10 items-center justify-center border-gray-200 border-l bg-white">
        <div className="pointer-events-none absolute top-0 bottom-0 -left-4 w-4 bg-linear-to-r from-transparent to-gray-300/30" />
        <MenuTrigger>
          <PopoverAnchor>
            <Button
              size="sm"
              shape="square"
              variant="ghost"
              data-testid={`actions-cell-${relationshipLabel}`}
            >
              <Icon icon={"mdi:dots-vertical"} className="text-gray-500" />
            </Button>
          </PopoverAnchor>

          <AriaPopover placement="bottom end">
            <Menu aria-label="Relationship actions">
              <MenuItem onAction={() => setShowPropertiesModal(true)}>
                <Icon icon="mdi:info-outline" className="text-base" />
                View properties
              </MenuItem>

              <MenuItem
                isDisabled={!isEditAllowed}
                tooltip={editTooltipMessage}
                onAction={() => setShowEditForm(true)}
              >
                <Icon icon="mdi:edit-outline" className="text-base" />
                Edit
              </MenuItem>

              {isDissociateAllowed && (
                <MenuItem
                  isDisabled={!isEditAllowed}
                  tooltip={editTooltipMessage}
                  onAction={() => setShowDissociateModal(true)}
                >
                  <Icon icon="mdi:link-variant-remove" className="text-base" />
                  Dissociate
                </MenuItem>
              )}
            </Menu>
          </AriaPopover>
        </MenuTrigger>
      </TableCell>

      <PopoverContent>
        <RelationshipProperties
          parentKind={parentKind}
          parentId={parentId}
          relationshipName={relationshipName}
          relationshipId={relationshipId}
        />
      </PopoverContent>

      <Sheet isOpen={showEditForm} onOpenChange={() => setShowEditForm(false)}>
        <SlideOverTitle
          schema={parentSchema}
          currentObjectLabel={relationshipLabel}
          title={`Edit ${relationshipLabel}`}
        />
        <ObjectItemEditComponent
          closeDrawer={() => setShowEditForm(false)}
          onUpdateComplete={async () => {
            await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
            setShowEditForm(false);
          }}
          objectId={relationshipId}
          objectname={relationshipKind}
        />
      </Sheet>

      {showDissociateModal && (
        <DissociateRelationshipsModal
          objectId={parentId}
          relationshipLabel={relationshipLabel}
          relationshipIds={[relationshipId]}
          relationshipName={relationshipName}
          isOpen={true}
          onOpenChange={setShowDissociateModal}
        />
      )}
    </Popover>
  );
}
