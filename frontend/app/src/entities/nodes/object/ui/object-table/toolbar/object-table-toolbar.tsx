import { ToolbarAddToGroupsAction } from "@/entities/nodes/object/ui/object-table/toolbar/actions/groups/toolbar-add-to-groups-action";
import { ToolBarRemoveFromGroupsAction } from "@/entities/nodes/object/ui/object-table/toolbar/actions/groups/toolbar-remove-from-groups-action";
import { ToolbarDeleteObject } from "@/entities/nodes/object/ui/object-table/toolbar/actions/objects/toolbar-delete-action";
import { ToolbarButton } from "@/entities/nodes/object/ui/object-table/toolbar/toolbar-button";
import { ToolbarDivider } from "@/entities/nodes/object/ui/object-table/toolbar/toolbar-divider";
import { NodeCore } from "@/entities/nodes/types";
import { classNames } from "@/shared/utils/common";
import { XIcon } from "lucide-react";

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
        "fixed bottom-10 left-1/2 -translate-x-1/2 z-10 whitespace-nowrap",
        "text backdrop-blur-lg px-1.5 shadow-lg rounded-xl border border-neutral-300 text-sm",
        "data-[entering]:animate-in data-[entering]:fade-in-0 data-[entering]:zoom-in-95 data-[entering]:slide-in-from-bottom-1/2",
        "data-[exiting]:duration-300 data-[exiting]:animate-out data-[exiting]:fade-out-0 data-[exiting]:zoom-out-95 data-[exiting]:slide-out-to-bottom-1/2",
        "flex items-center gap-1.5 outline-none"
      )}
    >
      <ToolbarButton variant="ghost" onPress={onClose}>
        <span>{selectedRows.length} selected</span>
        <XIcon className="size-3.5" />
      </ToolbarButton>

      <ToolbarDivider />

      <ToolbarAddToGroupsAction selectedRows={selectedRows} />
      <ToolBarRemoveFromGroupsAction selectedRows={selectedRows} />
      <ToolbarDeleteObject selectedRows={selectedRows} />

      {renderMore && (
        <>
          <ToolbarDivider />
          {renderMore({ selectedRows })}
        </>
      )}
    </div>
  );
}
