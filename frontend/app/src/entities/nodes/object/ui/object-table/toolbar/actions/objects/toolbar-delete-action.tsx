import { Trash2Icon } from "lucide-react";
import React from "react";

import { Button } from "@/shared/components/aria/button";
import { Tooltip } from "@/shared/components/aria/tooltip";

import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import type { NodeCore } from "@/entities/nodes/types";

import { DeleteObjectsModal } from "./delete-objects-modal";

export interface ToolbarDeleteActionProps {
  selectedRows: Array<NodeCore>;
}

export function ToolbarDeleteAction({ selectedRows }: ToolbarDeleteActionProps) {
  const [isOpen, setIsOpen] = React.useState(false);
  const { permission } = useObjectTableContext();
  const { isAllowed, message } = permission.delete;

  if (!isAllowed) {
    return (
      <Tooltip message={message}>
        <Button variant="danger-outline" size="xs" isDisabledAndFocusable>
          <Trash2Icon className="size-3" />
          Delete
        </Button>
      </Tooltip>
    );
  }

  return (
    <>
      <Button variant="danger-outline" size="xs" onPress={() => setIsOpen((prev) => !prev)}>
        <Trash2Icon className="size-3" />
        Delete
      </Button>

      <DeleteObjectsModal selectedRows={selectedRows} isOpen={isOpen} onOpenChange={setIsOpen} />
    </>
  );
}
