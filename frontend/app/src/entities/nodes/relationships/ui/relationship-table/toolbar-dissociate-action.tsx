import { Icon } from "@iconify-icon/react";
import React from "react";

import { ToolbarButton } from "@/entities/nodes/object/ui/object-table/toolbar/toolbar-button";
import {
  type DissociateRelationshipModalProps,
  DissociateRelationshipsModal,
} from "@/entities/nodes/relationships/ui/dissociate-relationships-modal";

export interface ToolBarRemoveFromGroupActionProps
  extends Omit<DissociateRelationshipModalProps, "open" | "setOpen"> {}

export function ToolbarDissociateAction({
  objectId,
  relationshipLabel,
  relationshipName,
  relationshipIds,
}: ToolBarRemoveFromGroupActionProps) {
  const [isOpen, setIsOpen] = React.useState(false);

  return (
    <>
      <ToolbarButton variant="danger" onPress={() => setIsOpen((prev) => !prev)}>
        <Icon icon="mdi:link-variant-remove" />
        Dissociate
      </ToolbarButton>

      <DissociateRelationshipsModal
        objectId={objectId}
        relationshipIds={relationshipIds}
        relationshipLabel={relationshipLabel}
        relationshipName={relationshipName}
        open={isOpen}
        setOpen={setIsOpen}
      />
    </>
  );
}
