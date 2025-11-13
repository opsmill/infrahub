import { useParams } from "react-router";

import type { DynamicRelationshipFieldProps } from "@/shared/components/form/type";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import type { RelationshipSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

import RelationshipField from "./relationship.field";

export interface RelationshipFieldProps extends DynamicRelationshipFieldProps {}

// Select kind (select 2 steps) if needed
const RelationshipParentConstraintField = ({ ...props }: RelationshipFieldProps) => {
  const { objectId, objectKind } = useParams();

  const { schema } = useSchema(objectKind);

  const parentRelationionshipSchema = schema?.relationships?.find((relationship) => {
    return relationship.name === props.schema.common_parent;
  });

  const { data, isPending } = useGetObject({
    objectId,
    objectSchema: schema,
    getRelationshipsVisible: (relationships: RelationshipSchema[]): RelationshipSchema[] => {
      return relationships.filter((relationship) => {
        return relationship.name === parentRelationionshipSchema?.name;
      });
    },
  });

  if (isPending) {
    return <LoadingIndicator />;
  }

  const currentRelationshipPeer = data?.[parentRelationionshipSchema?.name]?.node;

  if (!currentRelationshipPeer) {
    return <RelationshipField {...props} />;
  }

  return <RelationshipField {...props} defaultParent={currentRelationshipPeer} parentDisabled />;
};

export default RelationshipParentConstraintField;
