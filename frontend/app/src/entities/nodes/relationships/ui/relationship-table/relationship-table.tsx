import { Col } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { DataTable } from "@/shared/components/table/data-table";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import { QSP } from "@/shared/config/qsp";

import { IP_NAMESPACE_GENERIC } from "@/entities/ipam/ip-namespaces/domain/model/ip-namespace";
import { RELATIONSHIP_COLUMN_SURFACE } from "@/entities/nodes/columns/domain/model/column-surface";
import { useColumnVisibility } from "@/entities/nodes/columns/ui/hooks/use-column-visibility";
import { useFilters } from "@/entities/nodes/filters/ui/hooks/use-filters";
import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import { getObjectTableColumns } from "@/entities/nodes/object/ui/object-table/utils/get-object-table-columns";
import { canDissociateRelationship } from "@/entities/nodes/relationships/domain/rules/can-dissociate-relationship";
import {
  type UseObjectRelationshipsParams,
  useObjectRelationships,
} from "@/entities/nodes/relationships/ui/queries/get-object-relationships.query";
import { useGetRelationshipCount } from "@/entities/nodes/relationships/ui/queries/get-relationship-count.query";
import { getRelationshipActionsColumn } from "@/entities/nodes/relationships/ui/relationship-table/get-relationship-actions-column";
import { RelationshipTableToolbar } from "@/entities/nodes/relationships/ui/relationship-table/relationship-table-toolbar";
import { ToolbarDissociateAction } from "@/entities/nodes/relationships/ui/relationship-table/toolbar-dissociate-action";
import { useGetObjectPermissions } from "@/entities/permission/ui/queries/get-object-permissions.query";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export interface RelationshipTableProps extends UseObjectRelationshipsParams {}

export function RelationshipTable({
  relationshipSchema,
  parentId,
  relationshipName,
  parentKind,
  ...props
}: RelationshipTableProps) {
  const { schema: parentSchema } = useSchema(parentKind);
  const { data: permission } = useGetObjectPermissions(parentKind);
  const [filters] = useFilters();
  // The surface is named here rather than read from `ObjectTableContext`: two of the three hosts
  // render this table without a provider, and the one that does provide it carries the object
  // surface, whose `canReveal: true` would offer fields the relationship fetch never requests.
  const { columnVisibility } = useColumnVisibility(relationshipSchema, RELATIONSHIP_COLUMN_SURFACE);
  const { data: count } = useGetRelationshipCount({
    objectKind: parentKind,
    objectId: parentId,
    relationshipName,
  });

  const { data, fetchNextPage, error, hasNextPage, isPending, isFetchingNextPage } =
    useObjectRelationships({
      relationshipSchema,
      parentId,
      parentKind,
      relationshipName,
      filters,
      ...props,
    });

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const flatData = data?.pages?.flat() ?? [];

  // On an IP namespace's relationship tabs (e.g. its prefixes/addresses), the active
  // namespace lives in the route path, not the `namespace` query param that IPAM links
  // rely on. Forward it explicitly so child IP links stay in this namespace instead of
  // falling back to the default one.
  const identifierOverrideParams =
    parentSchema && isOfKind(IP_NAMESPACE_GENERIC, parentSchema)
      ? [{ name: QSP.IPAM_NAMESPACE, value: parentId }]
      : undefined;

  const columns = [
    ...getObjectTableColumns(relationshipSchema, { isDisabled: true }, identifierOverrideParams),
    getRelationshipActionsColumn({
      parentId,
      parentKind,
      relationshipName,
      permission,
      relationshipsCount: flatData.length,
    }),
  ];
  const isLoading = isPending || isFetchingNextPage;

  const isDissociateAllowed =
    parentSchema &&
    canDissociateRelationship({
      parentSchema,
      relationshipName,
      relationshipsCount: flatData.length,
    });

  return (
    <Col className="gap-0">
      <RelationshipTableToolbar schema={relationshipSchema} />

      <InfiniteScroll
        scrollX
        className="bg-table-frame"
        hasNextPage={hasNextPage}
        onLoadMore={fetchNextPage}
      >
        <DataTable
          columns={columns}
          columnVisibility={columnVisibility}
          count={count}
          data={flatData}
          isLoading={isLoading}
          renderEmpty={() => <ObjectTableEmpty schema={relationshipSchema} />}
          toolbarActions={
            isDissociateAllowed
              ? ({ selectedRows }) => {
                  return (
                    <ToolbarDissociateAction
                      objectId={parentId}
                      parentKind={parentKind}
                      relationshipIds={selectedRows.map((row) => row.id)}
                      relationshipName={relationshipName}
                      relationshipLabel="all selected rows"
                    />
                  );
                }
              : undefined
          }
        />
      </InfiniteScroll>
    </Col>
  );
}
