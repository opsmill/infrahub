import { ToolbarButton } from "@/entities/nodes/object/ui/object-table/toolbar/toolbar-button";
import { NodeCore } from "@/entities/nodes/types";
import { Icon } from "@iconify-icon/react";
import React from "react";
import { DeleteObjectsModal } from "./delete-objects-modal";

export interface ToolbarDeleteObjectProps {
  selectedRows: Array<NodeCore>;
}

export function ToolbarDeleteObject({ selectedRows }: ToolbarDeleteObjectProps) {
  const [isOpen, setIsOpen] = React.useState(false);

  return (
    <>
      <ToolbarButton variant="danger" onPress={() => setIsOpen((prev) => !prev)}>
        <Icon icon="mdi:trash-can-outline" />
        Delete
      </ToolbarButton>

      <DeleteObjectsModal selectedRows={selectedRows} open={isOpen} setOpen={setIsOpen} />
    </>
  );
}
