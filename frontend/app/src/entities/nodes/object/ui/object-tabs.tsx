import { Spinner } from "@infrahub/ui";

import { Badge } from "@/shared/components/ui/badge";
import { LinkTab } from "@/shared/components/ui/link";

import { useGetRelationshipCount } from "@/entities/nodes/relationships/ui/queries/get-relationship-count.query";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import type { RelationshipSchema } from "@/entities/schema/types";
import { useGetTaskCount } from "@/entities/tasks/ui/queries/get-task-count.query";

export interface RelationshipTabProps {
  objectKind: string;
  objectId: string;
  relationshipSchema: RelationshipSchema;
}

export function RelationshipTab({
  objectKind,
  objectId,
  relationshipSchema,
}: RelationshipTabProps) {
  const { isPending, data: relationshipCount } = useGetRelationshipCount({
    objectKind,
    objectId,
    relationshipName: relationshipSchema.name,
  });

  return (
    <LinkTab
      href={getObjectDetailsUrl(objectKind, objectId, undefined, relationshipSchema.name)}
      scrollIntoViewOnActive
    >
      {relationshipSchema.label}
      {isPending && <Spinner />}
      {!isPending && (
        <Badge className="rounded-full font-medium text-gray-80">{relationshipCount}</Badge>
      )}
    </LinkTab>
  );
}

export interface TabWithCountProps {
  objectKind: string;
  objectId: string;
}

export function ObjectTaskTab({ objectKind, objectId }: TabWithCountProps) {
  const { isPending, data: taskCount } = useGetTaskCount({ relatedNodeIds: [objectId] });

  return (
    <LinkTab
      href={getObjectDetailsUrl(objectKind, objectId, undefined, "tasks")}
      scrollIntoViewOnActive
    >
      Tasks
      {isPending ? (
        <Spinner />
      ) : (
        <Badge className="rounded-full font-medium text-gray-80">{taskCount}</Badge>
      )}
    </LinkTab>
  );
}
