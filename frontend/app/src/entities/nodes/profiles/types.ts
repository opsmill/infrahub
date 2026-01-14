import type { NumberAttribute } from "@/shared/api/graphql/generated/graphql";

import type { NodeObjectWithMetadata } from "@/entities/nodes/types";

export type ProfileData = NodeObjectWithMetadata & {
  profile_priority: NumberAttribute;
};
