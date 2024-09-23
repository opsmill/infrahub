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
  if (!relationshipData) {
    return { source: null, value: null };
  }

  if ("edges" in relationshipData) {
    return {
      source: {
        type: "user",
      },
      value: relationshipData.edges
        .map(({ node }) =>
          node
            ? {
                id: node.id,
                display_label: node.display_label,
                __typename: node.__typename,
              }
            : null
        )
        .filter((n) => !!n),
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

  // if filter form, we should only display user input
  if (isFilterForm) {
    return { source: null, value: null };
  }

  const source = relationshipData.properties.source;
  const sourceKind = source.__typename;

  const nodes = store.get(schemaState);
  const sourceSchema = nodes.find(({ kind }) => kind === sourceKind);

  if (sourceSchema && sourceSchema.inherit_from?.includes(RESOURCE_GENERIC_KIND)) {
    if (!relationshipData.node) {
      console.error("Source is a pool but node is null on relationship", relationshipData);
      return { source: null, value: null };
    }

    return {
      source: {
        type: "pool",
        label: source.display_label ?? null,
        id: source.id as string,
        kind: source.__typename as string,
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
