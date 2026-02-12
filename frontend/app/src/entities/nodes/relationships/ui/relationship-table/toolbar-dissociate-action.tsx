import { Icon } from "@iconify-icon/react";
import React from "react";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getActionAvailability } from "@/entities/branches/utils/get-action-tooltip";
import { ToolbarButtonWithTooltip } from "@/entities/nodes/object/ui/object-table/toolbar/toolbar-button";
import {
  type DissociateRelationshipModalProps,
  DissociateRelationshipsModal,
} from "@/entities/nodes/relationships/ui/dissociate-relationships-modal";

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
  const { isAllowed, tooltipMessage } = getActionAvailability(currentBranch.status, {
    isAllowed: true,
  });

  return (
    <>
      <ToolbarButtonWithTooltip
        variant="danger"
        isDisabled={!isAllowed}
        tooltipEnabled={!isAllowed}
        tooltipContent={tooltipMessage}
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
