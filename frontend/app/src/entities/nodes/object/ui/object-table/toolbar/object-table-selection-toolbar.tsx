import { NodeObject } from "@/entities/nodes/types";
import { classNames } from "@/shared/utils/common";
import { XIcon } from "lucide-react";
import {
  Button as AriaButton,
  Dialog as AriaDialog,
  Modal as AriaModal,
} from "react-aria-components";
import { ToolbarAddToGroupAction } from "@/entities/nodes/object/ui/object-table/toolbar/toolbar-add-to-group-action";

export interface ObjectTableSelectionToolbarProps {
  selectedRows: Array<NodeObject>;
  onClose: () => void;
}

export function ObjectTableSelectionToolbar({
  selectedRows,
  onClose,
}: ObjectTableSelectionToolbarProps) {
  return (
    <AriaModal
      isOpen
      className={classNames(
        "fixed bottom-10 left-1/2 -translate-x-1/2 z-50",
        "text backdrop-blur-lg p-2 shadow-lg rounded-2xl border border-neutral-300",
        "data-[entering]:animate-in data-[entering]:fade-in-0 data-[entering]:zoom-in-95 data-[entering]:slide-in-from-left-1/2",
        "data-[exiting]:duration-300 data-[exiting]:animate-out data-[exiting]:fade-out-0 data-[exiting]:zoom-out-95 data-[exiting]:slide-out-to-left-1/2"
      )}
    >
      <AriaDialog
        aria-label="Object table toolbar"
        className="flex items-center gap-2 outline-none"
      >
        <AriaButton
          onPress={onClose}
          className="inline-flex items-center gap-1.5 hover:bg-neutral-200/80 rounded-lg px-2 py-1 text-neutral-600"
        >
          <span>{selectedRows.length} selected</span>
          <XIcon className="size-3.5" />
        </AriaButton>

        <ToolbarAddToGroupAction selectedRows={selectedRows} />
        <AriaButton className="border rounded-lg px-2 py-1 border-red-600 text-red-600 hover:bg-neutral-50">
          Remove from group
        </AriaButton>
      </AriaDialog>
    </AriaModal>
  );
}
