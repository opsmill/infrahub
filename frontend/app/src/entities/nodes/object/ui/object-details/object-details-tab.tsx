import { Icon } from "@iconify-icon/react";

import { Badge } from "@/shared/components/ui/badge";
import { LinkTab } from "@/shared/components/ui/link";

import { constructPathForIpam } from "@/entities/ipam/ip-namespaces/ui/routing/ipam-urls";
import { useGetRelationshipCount } from "@/entities/nodes/relationships/ui/queries/get-relationship-count.query";
import type { RelationshipSchema } from "@/entities/schema/domain/model/schema";
import { getRelationshipDisplayLabel } from "@/entities/schema/domain/rules/get-relationship-display-label";
import { getSchemaIcon } from "@/entities/schema/domain/rules/get-schema-icon";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export interface ObjectDetailsTabProps {
  parentKind: string;
  parentId: string;
  relationship: RelationshipSchema;
  to?: string;
}

export function ObjectDetailsTab({
  parentKind,
  parentId,
  relationship,
  to,
}: ObjectDetailsTabProps) {
  const { data } = useGetRelationshipCount({
    objectKind: parentKind,
    objectId: parentId,
    relationshipName: relationship.name,
  });
  const { schema } = useSchema(relationship.peer);

  const url = to ?? constructPathForIpam(relationship.name);

  return (
    <LinkTab to={url}>
      <Icon icon={getSchemaIcon(schema)} />
      {getRelationshipDisplayLabel(relationship, schema)}
      <Badge variant="blue" className="rounded-full font-normal">
        {data}
      </Badge>
    </LinkTab>
  );
}
