import { type ColumnDef, createColumnHelper } from "@tanstack/react-table";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { DataTable } from "@/shared/components/table/data-table";
import { TableCell } from "@/shared/components/table/table-cell";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";

import type { NodeObject, NodeRelationship } from "@/entities/nodes/object/domain/model/node";
import { TableColumnHeader } from "@/entities/nodes/object/ui/object-table/cells/table-column-header";
import { TableRelationshipCell } from "@/entities/nodes/object/ui/object-table/cells/table-relationship-cell";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import { getObjectActionsColumn } from "@/entities/nodes/object/ui/object-table/utils/get-object-actions-column";
import {
  getObjectFieldsColumns,
  getObjectIdentifierColumns,
} from "@/entities/nodes/object/ui/object-table/utils/get-object-table-columns";
import { useObjects } from "@/entities/nodes/object/ui/queries/get-objects.query";
import { useObjectsCount } from "@/entities/nodes/object/ui/queries/get-objects-count.query";
import { useSort } from "@/entities/nodes/sort/ui/hooks/use-sort";
import { resolveDecisionFilters } from "@/entities/role-manager/domain/rules/resolve-decision-filters";
import {
  type DecisionOption,
  getDecisionOptions,
} from "@/entities/role-manager/domain/use-cases/get-decision-options";
import { getDecisionColumn } from "@/entities/role-manager/ui/get-decision-column";
import type { ModelSchema, RelationshipSchema } from "@/entities/schema/domain/model/schema";

const DECISION_ATTRIBUTE = "decision";

/** The identifier column already shows it as the node label. */
const NAME_ATTRIBUTE = "name";

const columnHelper = createColumnHelper<NodeObject>();

export interface RoleManagerObjectTableProps {
  /** Attributes to fetch; each one except `name` becomes a column, ordered as in the schema. */
  attributeNames: string[];
  /** Relationships to fetch and show as columns, ordered as in the schema. */
  relationshipNames: string[];
  /** Relationships the row Edit form loads in addition to its default fields. */
  editRelationshipNames?: string[];
}

export function RoleManagerObjectTable({
  attributeNames,
  relationshipNames,
  editRelationshipNames,
}: RoleManagerObjectTableProps) {
  const { filters: rawFilters, selectedSchema, permission } = useObjectTableContext();
  const { customSort } = useSort(selectedSchema);
  const decisionOptions = getDecisionOptions(selectedSchema.kind, DECISION_ATTRIBUTE);
  const filters = decisionOptions
    ? resolveDecisionFilters(rawFilters, decisionOptions)
    : rawFilters;

  const { data: count } = useObjectsCount({
    objectKind: selectedSchema.kind!,
    filters,
  });

  const { data, fetchNextPage, hasNextPage, isPending, isFetchingNextPage, error } = useObjects({
    schema: selectedSchema,
    filters,
    sort: customSort,
    getAttributesVisible: (attributes) => attributes.filter((a) => attributeNames.includes(a.name)),
    getRelationshipsVisible: (relationships) =>
      relationships.filter((r) => relationshipNames.includes(r.name)),
  });

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const columns = [
    ...getRoleManagerTableColumns(selectedSchema, {
      attributeNames,
      relationshipNames,
      decisionOptions,
    }),
    getObjectActionsColumn(permission, { extraRelationshipNames: editRelationshipNames }),
  ];
  const rows = data?.pages.flat() ?? [];

  return (
    <InfiniteScroll
      scrollX
      className="bg-table-frame"
      hasNextPage={hasNextPage}
      onLoadMore={fetchNextPage}
    >
      <DataTable
        columns={columns}
        data={rows}
        count={count}
        isLoading={isPending || isFetchingNextPage}
        renderEmpty={() => <ObjectTableEmpty schema={selectedSchema} />}
      />
    </InfiniteScroll>
  );
}

function getRoleManagerTableColumns(
  schema: ModelSchema,
  {
    attributeNames,
    relationshipNames,
    decisionOptions,
  }: {
    attributeNames: string[];
    relationshipNames: string[];
    decisionOptions: DecisionOption[] | null;
  }
): Array<ColumnDef<NodeObject>> {
  const attributes = (schema.attributes ?? []).filter(
    ({ name }) => attributeNames.includes(name) && name !== NAME_ATTRIBUTE
  );
  const decisionAttribute = decisionOptions
    ? attributes.find(({ name }) => name === DECISION_ATTRIBUTE)
    : undefined;
  const relationships = (schema.relationships ?? []).filter(({ name }) =>
    relationshipNames.includes(name)
  );

  return [
    ...getObjectIdentifierColumns(schema),
    ...getObjectFieldsColumns(
      schema,
      undefined,
      attributes.filter((attribute) => attribute !== decisionAttribute)
    ),
    ...(decisionAttribute && decisionOptions
      ? [getDecisionColumn(decisionAttribute, decisionOptions)]
      : []),
    ...getRelationshipColumns(schema, relationships),
  ] as Array<ColumnDef<NodeObject>>;
}

function getRelationshipColumns(
  schema: ModelSchema,
  relationships: RelationshipSchema[]
): Array<ColumnDef<NodeObject>> {
  return relationships.map(
    (relationship) =>
      columnHelper.accessor(relationship.name, {
        header: () => <TableColumnHeader schema={schema} columnSchema={relationship} />,
        cell: ({ cell }) => {
          const relationshipData = cell.getValue() as NodeRelationship | undefined;
          // A cached list of the same kind can come from a query that did not select this relationship.
          if (!relationshipData) return null;
          return (
            <TableCell>
              <TableRelationshipCell
                relationshipSchema={relationship}
                relationshipData={relationshipData}
              />
            </TableCell>
          );
        },
      }) as ColumnDef<NodeObject>
  );
}
