import { Icon } from "@iconify-icon/react";
import React from "react";

import { ToolbarButton } from "@/entities/nodes/object/ui/object-table/toolbar/toolbar-button";
import type { NodeCore } from "@/entities/nodes/types";

import { DeleteObjectsModal } from "./delete-objects-modal";

export interface ToolbarDeleteActionProps {
  selectedRows: Array<NodeCore>;
}

export function ToolbarDeleteAction({ selectedRows }: ToolbarDeleteActionProps) {
  const [isOpen, setIsOpen] = React.useState(false);

  return (
    <>
      <ToolbarButton variant="danger" onPress={() => setIsOpen((prev) => !prev)}>
        <Icon icon="mdi:delete-outline" className="text-sm" />
        Delete
      </ToolbarButton>

      <DeleteObjectsModal selectedRows={selectedRows} isOpen={isOpen} onOpenChange={setIsOpen} />
    </>
  );
}
