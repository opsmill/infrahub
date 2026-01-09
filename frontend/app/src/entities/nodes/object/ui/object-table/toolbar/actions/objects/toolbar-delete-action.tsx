import { Trash2 } from "lucide-react";
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
        <Trash2 className="size-3.5" />
        Delete
      </ToolbarButton>

      <DeleteObjectsModal selectedRows={selectedRows} open={isOpen} setOpen={setIsOpen} />
    </>
  );
}
