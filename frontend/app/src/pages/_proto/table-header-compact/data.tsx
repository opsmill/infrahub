// PROTOTYPE design-jam table-header-compact — real data plumbing shared by every revision; holds no design.
import type { ColumnDef } from "@tanstack/react-table";
import type { ReactNode } from "react";

import type { NodeObject } from "@/entities/nodes/object/domain/model/node";
import { getObjectTableColumns } from "@/entities/nodes/object/ui/object-table/utils/get-object-table-columns";
import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";
import { useObjectRelationships } from "@/entities/nodes/relationships/ui/queries/get-object-relationships.query";
import { useGetRelationshipCount } from "@/entities/nodes/relationships/ui/queries/get-relationship-count.query";
import { getRelationshipActionsColumn } from "@/entities/nodes/relationships/ui/relationship-table/get-relationship-actions-column";
import { PERMISSION_DENY_ALL } from "@/entities/permission/domain/model/permission";
import { useGetObjectPermissions } from "@/entities/permission/ui/queries/get-object-permissions.query";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export const OBJECTS = {
  "device-interfaces": {
    kind: "InfraDevice",
    id: "18e2045f-9d12-4fec-3c20-c5126f9bc4bd",
    relationshipName: "interfaces",
    tabs: ["Details", "Artifacts", "Interfaces", "Bgp Sessions"],
    activeTab: "Interfaces",
  },
  "country-children": {
    kind: "LocationCountry",
    id: "18e2044f-cc2d-dc28-3c2a-c5121726a121",
    relationshipName: "children",
    tabs: ["Details", "Site"],
    activeTab: "Site",
  },
  "country-children-empty": {
    kind: "LocationCountry",
    id: "18e2044f-cb01-815f-3c2e-c517006aed1d",
    relationshipName: "children",
    tabs: ["Details", "Site"],
    activeTab: "Site",
  },
} as const;

export type ObjectKey = keyof typeof OBJECTS;

export const REPOSITORY = { kind: "CoreRepository", id: "18e0d1c6-f457-9070-3604-c5171c607026" };

export function useRelationshipTab(objectKey: ObjectKey, denyPermission: boolean) {
  const target = OBJECTS[objectKey];
  const { schema: parentSchema } = useSchema(target.kind);
  const relationship = parentSchema?.relationships?.find((r) => r.name === target.relationshipName);
  const { schema: relationshipSchema } = useSchema(relationship?.peer);
  const { data: realPermission } = useGetObjectPermissions(target.kind);
  const permission = denyPermission ? PERMISSION_DENY_ALL : realPermission;

  const { data: parentData } = useGetObject(
    { objectSchema: parentSchema!, objectId: target.id },
    { enabled: !!parentSchema }
  );

  const { data: count } = useGetRelationshipCount({
    objectKind: target.kind,
    objectId: target.id,
    relationshipName: target.relationshipName,
  });

  const relationships = useObjectRelationships(
    {
      relationshipSchema: relationshipSchema!,
      parentId: target.id,
      parentKind: target.kind,
      relationshipName: target.relationshipName,
      filters: [],
    },
    { enabled: !!relationshipSchema }
  );

  const rows = relationships.data?.pages?.flat() ?? [];

  const buildColumns = (actionsHeader?: () => ReactNode): ColumnDef<NodeObject>[] => {
    if (!relationshipSchema) return [];
    const actions = getRelationshipActionsColumn({
      parentId: target.id,
      parentKind: target.kind,
      relationshipName: target.relationshipName,
      permission,
      relationshipsCount: rows.length,
    });
    return [
      ...getObjectTableColumns(relationshipSchema, { headerProps: { isDisabled: true } }),
      actionsHeader ? { ...actions, header: actionsHeader } : actions,
    ] as ColumnDef<NodeObject>[];
  };

  return {
    target,
    parentSchema,
    parentData,
    relationshipSchema,
    permission,
    count,
    rows,
    isLoading: relationships.isPending || relationships.isFetchingNextPage,
    hasNextPage: relationships.hasNextPage,
    fetchNextPage: relationships.fetchNextPage,
    buildColumns,
  };
}
