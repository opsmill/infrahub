import { Icon } from "@iconify-icon/react";

import { Badge } from "@/shared/components/ui/badge";
import { LinkTab } from "@/shared/components/ui/link";

import { constructPathForIpam } from "@/entities/ipam/utils";
import { useGetRelationshipCount } from "@/entities/nodes/relationships/ui/queries/get-relationship-count.query";
import type { RelationshipSchema } from "@/entities/schema/domain/model/types";
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
      {relationship.label}
      <Badge variant="blue" className="rounded-full font-normal">
        {data}
      </Badge>
    </LinkTab>
  );
}
