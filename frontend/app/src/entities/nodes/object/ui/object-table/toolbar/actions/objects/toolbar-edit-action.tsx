import { PencilIcon } from "lucide-react";
import { DialogTrigger } from "react-aria-components";

import { Button } from "@/shared/components/aria/button";
import { Popover } from "@/shared/components/aria/popover";
import { Tooltip } from "@/shared/components/aria/tooltip";

import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { BulkEditObjects } from "@/entities/nodes/object/ui/object-table/toolbar/actions/objects/bulk-edit-objects";
import type { NodeCore } from "@/entities/nodes/types";

export interface ToolbarEditActionProps {
  selectedRows: Array<NodeCore>;
}

export function ToolbarEditAction({ selectedRows }: ToolbarEditActionProps) {
  const { permission } = useObjectTableContext();
  const { isAllowed, message } = permission.update;

  if (!isAllowed) {
    return (
      <Tooltip message={message}>
        <Button variant="outline" size="xs" isDisabledAndFocusable>
          <PencilIcon className="size-3" />
          Edit
        </Button>
      </Tooltip>
    );
  }

  return (
    <DialogTrigger>
      <Button variant="outline" size="xs">
        <PencilIcon className="size-3" />
        Edit
      </Button>

      <Popover placement="top start" className="border-transparent bg-transparent shadow-none">
        <BulkEditObjects selectedRows={selectedRows} />
      </Popover>
    </DialogTrigger>
  );
}
