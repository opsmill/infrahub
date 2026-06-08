import { type ColumnDef, createColumnHelper } from "@tanstack/react-table";

import { TableCell } from "@/shared/components/table/table-cell";

import type { NodeAttribute, NodeObject } from "@/entities/nodes/types";
import { DecisionColumnHeader } from "@/entities/role-manager/ui/decision-column-header";
import type { AttributeSchema } from "@/entities/schema/types";

const columnHelper = createColumnHelper<NodeObject>();

export function getDecisionColumn(
  decisionAttribute: AttributeSchema,
  options: Array<{ value: number; label: string }>
): ColumnDef<NodeObject> {
  return columnHelper.accessor("decision", {
    header: () => <DecisionColumnHeader attributeSchema={decisionAttribute} options={options} />,
    cell: ({ cell }) => {
      const attributeData = cell.getValue() as NodeAttribute | undefined;
      const value = attributeData?.value;
      const option = options.find((o) => o.value === value);
      return <TableCell>{option?.label}</TableCell>;
    },
  }) as ColumnDef<NodeObject>;
}
