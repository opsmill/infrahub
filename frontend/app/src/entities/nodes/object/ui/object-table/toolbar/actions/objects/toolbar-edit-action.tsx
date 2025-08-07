import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { BulkEditObjects } from "@/entities/nodes/object/ui/object-table/toolbar/actions/objects/bulk-edit-objects";
import { ToolbarButton } from "@/entities/nodes/object/ui/object-table/toolbar/toolbar-button";
import { NodeCore } from "@/entities/nodes/types";
import { Popover } from "@/shared/components/aria/popover";
import { PencilLineIcon } from "lucide-react";
import { DialogTrigger } from "react-aria-components";

export interface ToolbarEditActionProps {
  selectedRows: Array<NodeCore>;
}

export function ToolbarEditAction({ selectedRows }: ToolbarEditActionProps) {
  const { selectedSchema } = useObjectTableContext();

  return (
    <DialogTrigger>
      <ToolbarButton>
        <PencilLineIcon className="size-3.5" />
        Edit
      </ToolbarButton>

      <Popover placement="top start" className="bg-transparent shadow-none border-transparent">
        <BulkEditObjects schema={selectedSchema} selectedRows={selectedRows} />
      </Popover>
    </DialogTrigger>
  );
}
