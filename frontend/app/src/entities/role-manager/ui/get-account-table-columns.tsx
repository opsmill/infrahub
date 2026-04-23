import { type ColumnDef, createColumnHelper } from "@tanstack/react-table";

import { TableCell } from "@/shared/components/table/table-cell";

import { TableAttributeCell } from "@/entities/nodes/object/ui/object-table/cells/table-attribute-cell";
import { TableColumnHeader } from "@/entities/nodes/object/ui/object-table/cells/table-column-header";
import { TableIdentifierCell } from "@/entities/nodes/object/ui/object-table/cells/table-identifier-cell";
import { TableIdentifierHeader } from "@/entities/nodes/object/ui/object-table/cells/table-identifier-header";
import { TableRelationshipCell } from "@/entities/nodes/object/ui/object-table/cells/table-relationship-cell";
import { getToggleSelectedRowHandler } from "@/entities/nodes/object/ui/object-table/utils/get-toggle-selected-row-handler";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { NodeAttribute, NodeObject, NodeRelationship } from "@/entities/nodes/types";
import type { ModelSchema, RelationshipSchema } from "@/entities/schema/types";

export const ACCOUNT_TABLE_ATTRIBUTES = ["name", "description", "account_type", "status"];
export const ACCOUNT_TABLE_RELATIONSHIPS = ["member_of_groups"];

const columnHelper = createColumnHelper<NodeObject>();

export function getAccountTableColumns(schema: ModelSchema): Array<ColumnDef<NodeObject>> {
  const attributesVisible = (schema.attributes ?? []).filter(
    ({ name }) => ACCOUNT_TABLE_ATTRIBUTES.includes(name) && name !== "name"
  );
  const relationshipsVisible = (schema.relationships ?? []).filter(({ name }) =>
    ACCOUNT_TABLE_RELATIONSHIPS.includes(name)
  );

  return [
    columnHelper.accessor((node) => getNodeLabel(node), {
      id: "id",
      header: ({ table }) => (
        <TableIdentifierHeader
          schema={schema}
          isSelected={table.getIsAllRowsSelected()}
          isIndeterminate={table.getIsSomePageRowsSelected()}
          onChange={table.toggleAllRowsSelected}
        />
      ),
      cell: ({ cell, row, table }) => {
        const label = cell.getValue();
        return (
          <TableIdentifierCell
            objectKind={row.original.__typename}
            objectId={row.original.id}
            label={label}
            isSelected={row.getIsSelected()}
            onClickCheckbox={getToggleSelectedRowHandler({ row, table })}
          />
        );
      },
    }),
    ...attributesVisible.map((attribute) =>
      columnHelper.accessor(attribute.name, {
        header: () => <TableColumnHeader columnSchema={attribute} />,
        cell: ({ cell }) => {
          const attributeData = cell.getValue() as NodeAttribute | undefined;
          return (
            <TableCell>
              <TableAttributeCell attributeSchema={attribute} attributeData={attributeData} />
            </TableCell>
          );
        },
      })
    ),
    ...relationshipsVisible.map((relationship) =>
      columnHelper.accessor(relationship.name, {
        header: () => <TableColumnHeader columnSchema={relationship} />,
        cell: ({ cell }) => {
          const relationshipData = cell.getValue() as NodeRelationship | undefined;
          if (!relationshipData) return null;
          return (
            <TableCell>
              <TableRelationshipCell
                relationshipSchema={relationship as RelationshipSchema}
                relationshipData={relationshipData}
              />
            </TableCell>
          );
        },
      })
    ),
  ] as Array<ColumnDef<NodeObject>>;
}
