import { Icon } from "@iconify-icon/react";

import { Badge } from "@/shared/components/ui/badge";
import { LinkTab } from "@/shared/components/ui/link";

import { constructPathForIpam } from "@/entities/ipam/utils";
import { useGetRelationshipCount } from "@/entities/nodes/relationships/ui/queries/get-relationship-count.query";
import type { RelationshipSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { getSchemaIcon } from "@/entities/schema/utils/get-schema-icon";

export interface ObjectDetailsTabProps {
  parentKind: string;
  parentId: string;
  relationship: RelationshipSchema;
  href?: string;
}

export function ObjectDetailsTab({
  parentKind,
  parentId,
  relationship,
  href,
}: ObjectDetailsTabProps) {
  const { data } = useGetRelationshipCount({
    objectKind: parentKind,
    objectId: parentId,
    relationshipName: relationship.name,
  });
  const { schema } = useSchema(relationship.peer);

  const url = href ?? constructPathForIpam(relationship.name);

  return (
    <LinkTab href={url}>
      <Icon icon={getSchemaIcon(schema)} />
      {relationship.label}
      <Badge variant="blue" className="rounded-full font-normal">
        {data}
      </Badge>
    </LinkTab>
  );
}
