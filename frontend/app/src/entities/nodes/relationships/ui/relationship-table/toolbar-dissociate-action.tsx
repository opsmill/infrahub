import { Icon } from "@iconify-icon/react";
import React from "react";

import { ToolbarButtonWithTooltip } from "@/entities/nodes/object/ui/object-table/toolbar/toolbar-button";
import {
  type DissociateRelationshipModalProps,
  DissociateRelationshipsModal,
} from "@/entities/nodes/relationships/ui/dissociate-relationships-modal";
import { useGetObjectPermissions } from "@/entities/permission/domain/get-object-permissions.query";

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
