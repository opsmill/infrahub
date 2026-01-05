import { PencilLineIcon } from "lucide-react";
import { DialogTrigger } from "react-aria-components";

import { Popover } from "@/shared/components/aria/popover";

import { BulkEditObjects } from "@/entities/nodes/object/ui/object-table/toolbar/actions/objects/bulk-edit-objects";
import { ToolbarButton } from "@/entities/nodes/object/ui/object-table/toolbar/toolbar-button";
import type { NodeCore } from "@/entities/nodes/types";

export interface ToolbarEditActionProps {
  selectedRows: Array<NodeCore>;
}

export function ToolbarEditAction({ selectedRows }: ToolbarEditActionProps) {
  return (
    <DialogTrigger>
      <ToolbarButton>
        <PencilLineIcon className="size-3.5" />
        Edit
      </ToolbarButton>

      <Popover placement="top start" className="border-transparent bg-transparent shadow-none">
        <BulkEditObjects selectedRows={selectedRows} />
      </Popover>
    </DialogTrigger>
  );
}
