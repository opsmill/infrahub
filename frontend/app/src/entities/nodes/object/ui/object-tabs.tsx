import { Spinner } from "@infrahub/ui";

import { Badge } from "@/shared/components/ui/badge";
import { LinkTab } from "@/shared/components/ui/link";

import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import { useGetRelationshipCount } from "@/entities/nodes/relationships/ui/queries/get-relationship-count.query";
import type { RelationshipSchema } from "@/entities/schema/domain/model/schema";
import { getRelationshipLabel } from "@/entities/schema/domain/rules/get-relationship-label";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
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
  const { schema: peerSchema } = useSchema(relationshipSchema.peer);

  return (
    <LinkTab
      to={getObjectDetailsUrl(objectKind, objectId, undefined, relationshipSchema.name)}
      scrollIntoViewOnActive
    >
      {getRelationshipLabel(relationshipSchema, peerSchema)}
      {isPending && <Spinner />}
      {!isPending && (
        <Badge className="rounded-full font-medium text-subtle">{relationshipCount}</Badge>
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
      to={getObjectDetailsUrl(objectKind, objectId, undefined, "tasks")}
      scrollIntoViewOnActive
    >
      Tasks
      {isPending ? (
        <Spinner />
      ) : (
        <Badge className="rounded-full font-medium text-subtle">{taskCount}</Badge>
      )}
    </LinkTab>
  );
}
