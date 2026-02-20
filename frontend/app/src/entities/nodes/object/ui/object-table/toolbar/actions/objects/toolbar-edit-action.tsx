import { Icon } from "@iconify-icon/react";
import { DialogTrigger } from "react-aria-components";

import { Popover } from "@/shared/components/aria/popover";

import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { BulkEditObjects } from "@/entities/nodes/object/ui/object-table/toolbar/actions/objects/bulk-edit-objects";
import { ToolbarButtonWithTooltip } from "@/entities/nodes/object/ui/object-table/toolbar/toolbar-button";
import type { NodeCore } from "@/entities/nodes/types";

export interface ToolbarEditActionProps {
  selectedRows: Array<NodeCore>;
}

export function ToolbarEditAction({ selectedRows }: ToolbarEditActionProps) {
  const { permission } = useObjectTableContext();
  const { isAllowed, message } = permission.update;

  if (!isAllowed) {
    return (
      <ToolbarButtonWithTooltip isDisabled tooltipEnabled tooltipContent={message}>
        <Icon icon="mdi:edit-outline" className="text-sm" />
        Edit
      </ToolbarButtonWithTooltip>
    );
  }

  return (
    <DialogTrigger>
      <ToolbarButtonWithTooltip>
        <Icon icon="mdi:edit-outline" className="text-sm" />
        Edit
      </ToolbarButtonWithTooltip>

      <Popover placement="top start" className="border-transparent bg-transparent shadow-none">
        <BulkEditObjects selectedRows={selectedRows} />
      </Popover>
    </DialogTrigger>
  );
}
