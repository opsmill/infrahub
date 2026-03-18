import { FROM_RESOURCE_POOL_SUFFIX } from "@/shared/components/form/constants";

import { isNodeRelationshipOne } from "@/entities/nodes/object/utils/is-node-relationship-one";
import type { NodeObject, NodeRelationshipWithMetadata } from "@/entities/nodes/types";
import type { ModelSchema } from "@/entities/schema/types";
import { isTemplateSchema } from "@/entities/schema/utils/is-template-schema";

export function resolveRelationshipData({
  objectSchema,
  objectData,
  relationshipName,
}: {
  objectSchema: ModelSchema;
  objectData: NodeObject;
  relationshipName: string;
}): NodeRelationshipWithMetadata {
  const relationshipData = objectData[relationshipName] as NodeRelationshipWithMetadata;

  if (
    isTemplateSchema(objectSchema) &&
    isNodeRelationshipOne(relationshipData) &&
    !relationshipData.node
  ) {
    const poolData = objectData[`${relationshipName}${FROM_RESOURCE_POOL_SUFFIX}`];
    if (isNodeRelationshipOne(poolData)) {
      return poolData as NodeRelationshipWithMetadata;
    }
  }

  return relationshipData;
}
