import { Icon } from "@iconify-icon/react";
import React from "react";

import { Button } from "@/shared/components/aria/button";
import { Tooltip } from "@/shared/components/aria/tooltip";

import {
  type DissociateRelationshipModalProps,
  DissociateRelationshipsModal,
} from "@/entities/nodes/relationships/ui/dissociate-relationships-modal";
import { useGetObjectPermissions } from "@/entities/permission/ui/queries/get-object-permissions.query";

export interface ToolBarRemoveFromGroupActionProps
  extends Omit<DissociateRelationshipModalProps, "isOpen" | "onOpenChange"> {
  parentKind: string;
}

export function ToolbarDissociateAction({
  objectId,
  relationshipLabel,
  relationshipName,
  relationshipIds,
  parentKind,
}: ToolBarRemoveFromGroupActionProps) {
  const [isOpen, setIsOpen] = React.useState(false);
  const { data: permission } = useGetObjectPermissions(parentKind);
  const { isAllowed, message } = permission?.update ?? { isAllowed: false };

  if (!isAllowed) {
    return (
      <Tooltip message={message}>
        <Button variant="danger-outline" size="xs" isDisabledAndFocusable>
          <Icon icon="mdi:link-variant-remove" />
          Dissociate
        </Button>
      </Tooltip>
    );
  }

  return (
    <>
      <Button variant="danger-outline" size="xs" onPress={() => setIsOpen((prev) => !prev)}>
        <Icon icon="mdi:link-variant-remove" />
        Dissociate
      </Button>

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
