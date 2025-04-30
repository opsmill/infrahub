import { getObjectTableColumns } from "@/entities/nodes/object/ui/object-table/get-object-table-columns";
import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import {
  UseObjectRelationshipsParams,
  useObjectRelationships,
} from "@/entities/nodes/relationships/domain/get-object-relationships/get-object-relationships.query";
import { getRelationshipActionsColumn } from "@/entities/nodes/relationships/ui/relationship-table/get-relationship-actions-column";
import { PERMISSION_ALLOW_ALL } from "@/entities/permission/constants";
import { InfiniteDataTable } from "@/shared/components/table/infinite-data-table";
import useFilters from "@/shared/hooks/useFilters";
import React from "react";

export interface RelationshipTableProps extends UseObjectRelationshipsParams {}

export function RelationshipTable({
  relationshipSchema,
  parentId,
  relationshipName,
  parentKind,
  ...props
}: RelationshipTableProps) {
  const [filters] = useFilters();
  const { data, isPending, isFetchingNextPage, fetchNextPage, hasNextPage } =
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
        count: flatData.length,
      }),
    ];
  }, [relationshipSchema.hash, flatData.length]);

  return (
    <InfiniteDataTable
      columns={columns}
      data={flatData}
      isLoading={isPending || isFetchingNextPage}
      renderEmpty={() => <ObjectTableEmpty schema={relationshipSchema} />}
      hasNextPage={hasNextPage}
      fetchNextPage={fetchNextPage}
    />
  );
}
