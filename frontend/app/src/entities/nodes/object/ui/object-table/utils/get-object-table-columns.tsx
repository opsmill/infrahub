import { type ColumnDef, createColumnHelper } from "@tanstack/react-table";

import type { overrideQueryParams } from "@/shared/api/rest/fetch";
import { FROM_RESOURCE_POOL_SUFFIX } from "@/shared/components/form/constants";
import { TableCell } from "@/shared/components/table/table-cell";
import { sortByOrderWeight } from "@/shared/utils/common";

import { IP_ADDRESS_AVAILABLE_KIND } from "@/entities/ipam/ip-addresses/domain/model/ip-address";
import { IP_PREFIX_AVAILABLE_KIND } from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix";
import type {
  NodeAttribute,
  NodeObject,
  NodeRelationship,
  NodeRelationshipOne,
} from "@/entities/nodes/object/domain/model/node";
import { getAttributesVisibleInListView } from "@/entities/nodes/object/domain/rules/get-attributes-visible-in-list-view";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/domain/rules/get-relationships-visible-in-list-view";
import { isFromResourcePoolRelationship } from "@/entities/nodes/object/domain/rules/is-from-resource-pool-relationship";
import { resolveRelationshipData } from "@/entities/nodes/object/domain/rules/resolve-relationship-data";
import { KindBodyCell } from "@/entities/nodes/object/ui/object-table/cells/generics/kind-body-cell";
import { KindHeaderCell } from "@/entities/nodes/object/ui/object-table/cells/generics/kind-header-cell";
import { TableAttributeCell } from "@/entities/nodes/object/ui/object-table/cells/table-attribute-cell";
import {
  TableColumnHeader,
  type TableColumnHeaderProps,
} from "@/entities/nodes/object/ui/object-table/cells/table-column-header";
import { TableIdentifierCell } from "@/entities/nodes/object/ui/object-table/cells/table-identifier-cell";
import { TableIdentifierHeader } from "@/entities/nodes/object/ui/object-table/cells/table-identifier-header";
import {
  RelationshipNodeDisplay,
  TableRelationshipCell,
} from "@/entities/nodes/object/ui/object-table/cells/table-relationship-cell";
import { getToggleSelectedRowHandler } from "@/entities/nodes/object/ui/object-table/utils/get-toggle-selected-row-handler";
import type {
  AttributeSchema,
  ModelSchema,
  RelationshipSchema,
} from "@/entities/schema/domain/model/schema";
import { isGenericSchema } from "@/entities/schema/domain/rules/is-generic-schema";
import { isRelationshipSchema } from "@/entities/schema/domain/rules/is-relationship-schema";

const columnHelper = createColumnHelper<NodeObject>();

export function getObjectIdentifierColumns(
  schema: ModelSchema,
  identifierOverrideParams?: overrideQueryParams[]
): Array<ColumnDef<NodeObject, string>> {
  return [
    columnHelper.accessor((node) => getNodeLabel(node), {
      id: "id",
      header: ({ table }) => {
        return (
          <TableIdentifierHeader
            schema={schema}
            isSelected={table.getIsAllRowsSelected()}
            isIndeterminate={table.getIsSomePageRowsSelected()}
            onChange={table.toggleAllRowsSelected}
          />
        );
      },
      cell: ({ cell, row, table }) => {
        const label = cell.getValue() ?? "-";

        return (
          <TableIdentifierCell
            objectKind={row.original.__typename}
            objectId={row.original.id}
            label={label}
            isSelected={row.getIsSelected()}
            onClickCheckbox={getToggleSelectedRowHandler({ row, table })}
            overrideParams={identifierOverrideParams}
          />
        );
      },
    }),
  ];
}

export function getObjectGenericColumns(schema: ModelSchema): Array<ColumnDef<NodeObject, string>> {
  return isGenericSchema(schema)
    ? [
        columnHelper.accessor("__typename", {
          id: "objectKind",
          header: () => {
            return <KindHeaderCell schema={schema} />;
          },
          cell: ({ cell }) => {
            const schemaKind = cell.getValue();
            if (schemaKind === IP_ADDRESS_AVAILABLE_KIND) return null;
            if (schemaKind === IP_PREFIX_AVAILABLE_KIND) return null;

            return <KindBodyCell schemaKind={schemaKind} />;
          },
        }),
      ]
    : [];
}

function getDefaultFieldsColumnSchemas(
  schema: ModelSchema
): Array<AttributeSchema | RelationshipSchema> {
  const attributes = getAttributesVisibleInListView(schema.attributes ?? []);
  const relationships = getRelationshipsVisibleInListView(schema.relationships ?? []).filter(
    (rel) => !isFromResourcePoolRelationship(rel.name)
  );
  return sortByOrderWeight([...attributes, ...relationships]);
}

export function getObjectFieldsColumns(
  schema: ModelSchema,
  headerProps?: Partial<TableColumnHeaderProps>,
  fields?: Array<AttributeSchema | RelationshipSchema>
): Array<ColumnDef<NodeObject, NodeAttribute | NodeRelationship>> {
  // When `fields` is provided the caller has already resolved and ordered the field list,
  // so we build a column for each one instead of deriving the default visible set here.
  const sortedColumns = fields ?? getDefaultFieldsColumnSchemas(schema);

  return sortedColumns.map((columnSchema) => {
    return columnHelper.accessor(columnSchema.name, {
      header: () => {
        return <TableColumnHeader schema={schema} columnSchema={columnSchema} {...headerProps} />;
      },
      cell: ({ cell, row }) => {
        const value = cell.getValue();
        if (isRelationshipSchema(columnSchema)) {
          return (
            <TableCell>
              <TableRelationshipCell
                relationshipSchema={columnSchema}
                relationshipData={resolveRelationshipData({
                  objectSchema: schema,
                  objectData: row.original,
                  relationshipName: columnSchema.name,
                })}
              />
            </TableCell>
          );
        }
        const fromResourcePoolRelationshipName = columnSchema.name + FROM_RESOURCE_POOL_SUFFIX;
        const fromResourcePoolData = row.original[fromResourcePoolRelationshipName] as
          | NodeRelationshipOne
          | undefined;

        if (fromResourcePoolData?.node) {
          return (
            <TableCell>
              <RelationshipNodeDisplay node={fromResourcePoolData.node} />
            </TableCell>
          );
        }

        return (
          <TableCell>
            <TableAttributeCell
              attributeSchema={columnSchema}
              attributeData={value as NodeAttribute}
            />
          </TableCell>
        );
      },
    });
  });
}

export const getObjectTableColumns = (
  schema: ModelSchema,
  headerProps?: Partial<TableColumnHeaderProps>,
  identifierOverrideParams?: overrideQueryParams[],
  fields?: Array<AttributeSchema | RelationshipSchema>
): Array<ColumnDef<NodeObject>> => {
  return [
    ...getObjectIdentifierColumns(schema, identifierOverrideParams),
    ...getObjectGenericColumns(schema),
    ...getObjectFieldsColumns(schema, headerProps, fields),
  ] as Array<ColumnDef<NodeObject>>;
};
