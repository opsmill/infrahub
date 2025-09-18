import { Icon } from "@iconify-icon/react";
import { useState } from "react";

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
import { Popover, PopoverAnchor, PopoverContent } from "@/shared/components/ui/popover";
import { Tooltip } from "@/shared/components/ui/tooltip";

import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
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

  const isEditAllowed = permission.update.isAllowed;
  const isDissociateAllowed = canDissociateRelationship({
    parentSchema,
    relationshipName,
    relationshipsCount,
  });

  return (
    <Popover open={showPropertiesModal} onOpenChange={setShowPropertiesModal}>
      <TableCell className="-ml-px sticky right-0 size-10 items-center justify-center border-gray-200 border-l bg-white">
        <div className="-left-4 pointer-events-none absolute top-0 bottom-0 w-4 bg-linear-to-r from-transparent to-gray-300/30" />
        <DropdownMenu>
          <PopoverAnchor>
            <DropdownMenuTrigger asChild>
              <Button
                size="square"
                variant="ghost"
                className="size-6"
                data-testid={`actions-cell-${relationshipLabel}`}
              >
                <Icon icon={"mdi:dots-vertical"} className="text-gray-500" />
              </Button>
            </DropdownMenuTrigger>
          </PopoverAnchor>

          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => setShowPropertiesModal(true)}>
              <Icon icon="mdi:info-outline" className="text-base" />
              View properties
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

            {isDissociateAllowed && (
              <Tooltip enabled={!isEditAllowed} content={permission.update.message} side="left">
                <div>
                  <DropdownMenuItem
                    disabled={!isEditAllowed}
                    onClick={() => isEditAllowed && setShowDissociateModal(true)}
                  >
                    <Icon icon="mdi:link-variant-remove" className="text-base" />
                    Dissociate
                  </DropdownMenuItem>
                </div>
              </Tooltip>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </TableCell>

      <PopoverContent>
        <RelationshipProperties
          parentKind={parentKind}
          parentId={parentId}
          relationshipName={relationshipName}
          relationshipId={relationshipId}
        />
      </PopoverContent>

      {showEditForm && (
        <SlideOver
          title={
            <SlideOverTitle
              schema={parentSchema}
              currentObjectLabel={relationshipLabel}
              title={`Edit ${relationshipLabel}`}
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
            objectid={relationshipId}
            objectname={relationshipKind}
          />
        </SlideOver>
      )}

      {showDissociateModal && (
        <DissociateRelationshipsModal
          objectId={parentId}
          relationshipLabel={relationshipLabel}
          relationshipIds={[relationshipId]}
          relationshipName={relationshipName}
          open={true}
          setOpen={() => setShowDissociateModal(false)}
        />
      )}
    </Popover>
  );
}
