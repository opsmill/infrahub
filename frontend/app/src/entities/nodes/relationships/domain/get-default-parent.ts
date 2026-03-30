import type { ContextParams } from "@/shared/api/types";
import type { FormRelationshipValue } from "@/shared/components/form/type";
import type { FormContextType } from "@/shared/components/form/utils/form-context";

import { getDefaultParentFromApi } from "@/entities/nodes/relationships/api/get-default-parent-from-api";
import type { NodeCore, NodeObject } from "@/entities/nodes/types";
import type { ModelSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

export interface UseDefaultParentParams {
  defaultValue?: FormRelationshipValue;
  parentRelationship?: {
    peer?: string;
    direction?: "bidirectional" | "inbound" | "outbound";
    identifier?: string;
  };
}

export interface DefaultParentParams
  extends UseDefaultParentParams,
    ContextParams,
    FormContextType {}

const convertNodeObjectToNode = (nodeObject: NodeObject | null | undefined): NodeCore | null => {
  if (!nodeObject) return null;
  return {
    id: nodeObject.id,
    display_label: nodeObject.display_label || nodeObject.id,
    __typename: nodeObject.__typename,
  };
};

export const getDefaultParent = async ({
  defaultValue,
  parentRelationship,
  parentSchema,
  parentData,
  branchName,
  atDate,
}: DefaultParentParams) => {
  const { data, error } = await getDefaultParentFromApi({
    defaultValue,
    parentRelationship: parentRelationship || {},
    branchName,
    atDate,
  });

  if (error) throw error;

  const currentParent =
    parentRelationship?.peer && data && data[parentRelationship?.peer]?.edges[0]?.node;

  if (currentParent) {
    return currentParent;
  }

  if (
    parentRelationship?.peer &&
    parentSchema &&
    isOfKind(parentRelationship?.peer, parentSchema as ModelSchema)
  ) {
    return convertNodeObjectToNode(parentData);
  }

  return null;
};
