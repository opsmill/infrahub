import { FormRelationshipValue } from "@/components/form/type";
import { RelationshipType } from "@/utils/getObjectItemDisplayValue";
import { store } from "@/state";
import { schemaState } from "@/state/atoms/schema.atom";
import { RESOURCE_GENERIC_KIND } from "@/screens/resource-manager/constants";

type GetRelationshipDefaultValueParams = {
  relationshipData: RelationshipType | undefined;
  isFilterForm?: boolean;
};

export const getRelationshipDefaultValue = ({
  isFilterForm,
  relationshipData,
}: GetRelationshipDefaultValueParams): FormRelationshipValue => {
  if (isFilterForm) {
    return { source: null, value: null };
  }

  if (!relationshipData) {
    return { source: null, value: null };
  }

  if ("edges" in relationshipData) {
    return {
      source: {
        type: "user",
      },
      value: relationshipData.edges.map(({ node }) => ({
        id: node?.id!,
      })),
    };
  }

  if (!relationshipData.properties?.source?.__typename) {
    return {
      source: {
        type: "user",
      },
      value: relationshipData.node,
    };
  }

  const source = relationshipData.properties.source;
  const sourceKind = source.__typename;

  const nodes = store.get(schemaState);
  const sourceSchema = nodes.find(({ kind }) => kind === sourceKind);

  if (sourceSchema && sourceSchema.inherit_from?.includes(RESOURCE_GENERIC_KIND)) {
    return {
      source: {
        type: "pool",
        label: source.display_label,
      },
      value: relationshipData.node,
    };
  }

  return {
    source: {
      type: "user",
    },
    value: relationshipData.node,
  };
};
