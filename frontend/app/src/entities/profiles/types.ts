import type { NumberAttribute } from "@/shared/api/graphql/generated/graphql";

import type { AttributeType } from "@/entities/nodes/getObjectItemDisplayValue";

export interface ProfileData {
  [key: string]: string | Pick<AttributeType, "value" | "__typename">;
  display_label: string;
  id: string;
  __typename: string;
  profile_priority: NumberAttribute;
}

export interface ProfileAttributeField {
  name: string;
  kind: string;
}

export interface ProfileRelationshipField {
  name: string;
  paginated: boolean;
}

export interface ProfileQueryParams {
  name: string;
  attributes: ProfileAttributeField[];
  relationships: ProfileRelationshipField[];
}
