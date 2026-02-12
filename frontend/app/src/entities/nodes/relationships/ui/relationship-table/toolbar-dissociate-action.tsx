import { Icon } from "@iconify-icon/react";
import React from "react";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { ToolbarButtonWithTooltip } from "@/entities/nodes/object/ui/object-table/toolbar/toolbar-button";
import {
  type DissociateRelationshipModalProps,
  DissociateRelationshipsModal,
} from "@/entities/nodes/relationships/ui/dissociate-relationships-modal";
import { getPermission } from "@/entities/permission/utils";

export interface ToolBarRemoveFromGroupActionProps
  extends Omit<DissociateRelationshipModalProps, "isOpen" | "onOpenChange"> {}

export function ToolbarDissociateAction({
  objectId,
  relationshipLabel,
  relationshipName,
  relationshipIds,
}: ToolBarRemoveFromGroupActionProps) {
  const [isOpen, setIsOpen] = React.useState(false);
  const { currentBranch } = useCurrentBranch();
  const permission = getPermission(undefined, { branch: currentBranch });
  const { isAllowed, message } = permission.update;

  return (
    <>
      <ToolbarButtonWithTooltip
        variant="danger"
        isDisabled={!isAllowed}
        tooltipEnabled={!isAllowed}
        tooltipContent={message}
        onPress={() => setIsOpen((prev) => !prev)}
      >
        <Icon icon="mdi:link-variant-remove" />
        Dissociate
      </ToolbarButtonWithTooltip>

      <DissociateRelationshipsModal
        objectId={objectId}
        relationshipIds={relationshipIds}
        relationshipLabel={relationshipLabel}
        relationshipName={relationshipName}
        isOpen={isOpen}
        onOpenChange={setIsOpen}
      />
    </>
  );
}
