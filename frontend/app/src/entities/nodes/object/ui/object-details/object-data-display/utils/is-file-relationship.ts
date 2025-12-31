import { FILE_GENERIC_KIND } from "@/shared/config/constants";

import { getSchema } from "@/entities/schema/domain/get-schema";
import type { RelationshipSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

export function isFileRelationship(relationshipSchema: RelationshipSchema): boolean {
  const { schema: peerSchema } = getSchema(relationshipSchema.peer);

  if (!peerSchema) {
    return false;
  }

  return isOfKind(FILE_GENERIC_KIND, peerSchema);
}
