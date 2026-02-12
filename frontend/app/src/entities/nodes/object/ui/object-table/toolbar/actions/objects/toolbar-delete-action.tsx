import { Icon } from "@iconify-icon/react";
import React from "react";

import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ToolbarButtonWithTooltip } from "@/entities/nodes/object/ui/object-table/toolbar/toolbar-button";
import type { NodeCore } from "@/entities/nodes/types";

import { DeleteObjectsModal } from "./delete-objects-modal";

export interface ToolbarDeleteActionProps {
  selectedRows: Array<NodeCore>;
}

export function ToolbarDeleteAction({ selectedRows }: ToolbarDeleteActionProps) {
  const [isOpen, setIsOpen] = React.useState(false);
  const { permission } = useObjectTableContext();
  const { isAllowed, message } = permission.delete;

  return (
    <>
      <ToolbarButtonWithTooltip
        variant="danger"
        isDisabled={!isAllowed}
        tooltipEnabled={!isAllowed}
        tooltipContent={message}
        onPress={() => setIsOpen((prev) => !prev)}
      >
        <Icon icon="mdi:delete-outline" className="text-sm" />
        Delete
      </ToolbarButtonWithTooltip>

      <DeleteObjectsModal selectedRows={selectedRows} isOpen={isOpen} onOpenChange={setIsOpen} />
    </>
  );
}
