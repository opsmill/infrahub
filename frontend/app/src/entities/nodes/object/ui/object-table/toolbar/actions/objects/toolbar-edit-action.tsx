import { Icon } from "@iconify-icon/react";
import { DialogTrigger } from "react-aria-components";

import { Popover } from "@/shared/components/aria/popover";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getActionAvailability } from "@/entities/branches/utils/get-action-tooltip";
import { BulkEditObjects } from "@/entities/nodes/object/ui/object-table/toolbar/actions/objects/bulk-edit-objects";
import { ToolbarButtonWithTooltip } from "@/entities/nodes/object/ui/object-table/toolbar/toolbar-button";
import type { NodeCore } from "@/entities/nodes/types";

export interface ToolbarEditActionProps {
  selectedRows: Array<NodeCore>;
}

export function ToolbarEditAction({ selectedRows }: ToolbarEditActionProps) {
  const { currentBranch } = useCurrentBranch();
  const { isAllowed, tooltipMessage } = getActionAvailability(currentBranch.status, {
    isAllowed: true,
  });

  if (!isAllowed) {
    return (
      <ToolbarButtonWithTooltip isDisabled tooltipEnabled tooltipContent={tooltipMessage}>
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
