import { useGetRelationshipCount } from "@/entities/nodes/relationships/domain/get-relationship-count/get-relationship-count.query";
import { RelationshipSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { getSchemaIcon } from "@/entities/schema/utils/get-schema-icon";
import { constructPath } from "@/shared/api/rest/fetch";
import { Badge } from "@/shared/components/ui/badge";
import { LinkTab } from "@/shared/components/ui/link";
import { Icon } from "@iconify-icon/react";

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

  const url = href ?? constructPath(relationship.name);

  return (
    <LinkTab href={url}>
      <Icon icon={getSchemaIcon(schema)} />
      {relationship.label}
      <Badge variant="blue" className="font-normal rounded-full">
        {data}
      </Badge>
    </LinkTab>
  );
}
