import React from "react";

import { DataTable } from "@/shared/components/table/data-table";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import useFilters from "@/shared/hooks/useFilters";

import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import { getObjectTableColumns } from "@/entities/nodes/object/ui/object-table/utils/get-object-table-columns";
import {
  type UseObjectRelationshipsParams,
  useObjectRelationships,
} from "@/entities/nodes/relationships/domain/get-object-relationships/get-object-relationships.query";
import { getRelationshipActionsColumn } from "@/entities/nodes/relationships/ui/relationship-table/get-relationship-actions-column";
import { ToolbarDissociateAction } from "@/entities/nodes/relationships/ui/relationship-table/toolbar-dissociate-action";
import { canDissociateRelationship } from "@/entities/nodes/relationships/utils/can-dissociate-relationship";
import { PERMISSION_ALLOW_ALL } from "@/entities/permission/constants";
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
  const [filters] = useFilters();
  const { data, fetchNextPage, hasNextPage, isPending, isFetchingNextPage } =
    useObjectRelationships({
      relationshipSchema,
      parentId,
      parentKind,
      relationshipName,
      filters,
      ...props,
    });

  const flatData = React.useMemo(() => data?.pages?.flat() ?? [], [data]);

  const columns = React.useMemo(() => {
    return [
      ...getObjectTableColumns(relationshipSchema, { disabled: true }),
      getRelationshipActionsColumn({
        parentId,
        parentKind,
        relationshipName,
        permission: PERMISSION_ALLOW_ALL,
        relationshipsCount: flatData.length,
      }),
    ];
  }, [relationshipSchema.hash, flatData.length]);

  const isLoading = isPending || isFetchingNextPage;

  const isDissociateAllowed =
    parentSchema &&
    canDissociateRelationship({
      parentSchema,
      relationshipName,
      relationshipsCount: flatData.length,
    });

  return (
    <InfiniteScroll scrollX hasNextPage={hasNextPage} onLoadMore={fetchNextPage}>
      <DataTable
        columns={columns}
        data={flatData}
        isLoading={isLoading}
        renderEmpty={() => <ObjectTableEmpty schema={relationshipSchema} />}
        toolbarActions={
          isDissociateAllowed
            ? ({ selectedRows }) => {
                return (
                  <ToolbarDissociateAction
                    objectId={parentId}
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
  );
}
