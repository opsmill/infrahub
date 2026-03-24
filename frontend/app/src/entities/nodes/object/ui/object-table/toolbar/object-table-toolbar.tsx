import { XIcon } from "lucide-react";

import { classNames } from "@/shared/utils/common";

import { ToolbarAddToGroupsAction } from "@/entities/nodes/object/ui/object-table/toolbar/actions/groups/toolbar-add-to-groups-action";
import { ToolBarRemoveFromGroupsAction } from "@/entities/nodes/object/ui/object-table/toolbar/actions/groups/toolbar-remove-from-groups-action";
import { ToolbarDeleteAction } from "@/entities/nodes/object/ui/object-table/toolbar/actions/objects/toolbar-delete-action";
import { ToolbarEditAction } from "@/entities/nodes/object/ui/object-table/toolbar/actions/objects/toolbar-edit-action";
import { ToolbarButton } from "@/entities/nodes/object/ui/object-table/toolbar/toolbar-button";
import { ToolbarDivider } from "@/entities/nodes/object/ui/object-table/toolbar/toolbar-divider";
import type { NodeCore } from "@/entities/nodes/types";

export interface ObjectTableSelectionToolbarProps {
  selectedRows: Array<NodeCore>;
  onClose: () => void;
  renderMore?: (props: { selectedRows: Array<NodeCore> }) => React.ReactNode;
}

export function ObjectTableToolbar({
  selectedRows,
  onClose,
  renderMore,
}: ObjectTableSelectionToolbarProps) {
  return (
    <div
      role="dialog"
      className={classNames(
        "fixed bottom-10 left-1/2 z-10 -translate-x-1/2 whitespace-nowrap",
        "text rounded-xl border border-neutral-300 px-1.5 text-sm shadow-lg backdrop-blur-lg",
        "fade-in-0 zoom-in-95 slide-in-from-bottom-1/2 animate-in",
        "flex items-center gap-1.5 outline-none"
      )}
      data-testid="object-table-toolbar"
    >
      <ToolbarButton variant="ghost" onPress={onClose}>
        <span>{selectedRows.length} selected</span>
        <XIcon className="size-3.5" />
      </ToolbarButton>

      <ToolbarDivider />

      <ToolbarEditAction selectedRows={selectedRows} />
      <ToolbarAddToGroupsAction selectedRows={selectedRows} />
      <ToolBarRemoveFromGroupsAction selectedRows={selectedRows} />
      <ToolbarDeleteAction selectedRows={selectedRows} />

      {renderMore && (
        <>
          <ToolbarDivider />
          {renderMore({ selectedRows })}
        </>
      )}
    </div>
  );
}
