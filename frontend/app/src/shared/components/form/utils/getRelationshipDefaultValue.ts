import { RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { NodeRelationship } from "@/entities/nodes/types";
import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/constants";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import {
  EmptyFieldValue,
  FormRelationshipValue,
  RelationshipValueFromPool,
  RelationshipValueFromTemplate,
  RelationshipValueFromUser,
} from "@/shared/components/form/type";
import { store } from "@/shared/stores";

type GetRelationshipDefaultValueParams = {
  relationshipData: RelationshipType | undefined;
  relationshipTemplate: NodeRelationship | undefined;
  isFilterForm?: boolean;
  peerField?: string;
};

export const getRelationshipDefaultValue = ({
  isFilterForm,
  relationshipData,
  relationshipTemplate,
  peerField,
}: GetRelationshipDefaultValueParams): FormRelationshipValue => {
  if (isFilterForm) {
    return { source: null, value: null };
  }

  if (relationshipData) {
    return getRelationshipDefaultValueFromData(relationshipData, peerField);
  }

  if (relationshipTemplate) {
    return getRelationshipDefaultValueFromTemplate(relationshipTemplate);
  }

  return { source: null, value: null };
};

export const getRelationshipDefaultValueFromData = (
  relationshipData: RelationshipType,
  peerField?: string
): RelationshipValueFromUser | RelationshipValueFromPool | EmptyFieldValue => {
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
                ...(peerField ? { [peerField]: node[peerField] ?? node[peerField] } : {}),
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

  const source = relationshipData.properties.source;
  const sourceKind = source.__typename;

  const nodes = store.get(nodeSchemasAtom);
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

export const getRelationshipDefaultValueFromTemplate = (
  relationshipTemplate: NodeRelationship
): RelationshipValueFromTemplate => {
  if ("edges" in relationshipTemplate) {
    return {
      source: {
        type: "template",
      },
      value: relationshipTemplate.edges
        .map(({ node }) =>
          node
            ? {
                id: node.id,
                display_label: getNodeLabel(node),
                __typename: node.__typename,
              }
            : null
        )
        .filter((n) => !!n),
    };
  }

  const { node } = relationshipTemplate;

  return {
    source: {
      type: "template",
    },
    value: {
      id: node.id,
      display_label: getNodeLabel(node),
      __typename: node.__typename,
    },
  };
};
