import { FROM_RESOURCE_POOL_SUFFIX } from "@/shared/components/form/constants";

import type {
  NodeObject,
  NodeRelationshipWithMetadata,
} from "@/entities/nodes/object/domain/model/node";
import { isNodeRelationshipOne } from "@/entities/nodes/object/domain/rules/is-node-relationship-one";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { isTemplateSchema } from "@/entities/schema/domain/rules/is-template-schema";

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
