import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import type {
  EmptyFieldValue,
  FormRelationshipValue,
  RelationshipValueFromPool,
  RelationshipValueFromTemplate,
  RelationshipValueFromUser,
  TemplateSource,
} from "@/shared/components/form/type";
import { store } from "@/shared/stores";

import type { RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { NodeObject, NodeRelationship } from "@/entities/nodes/types";
import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/constants";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import type { ModelSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

type GetRelationshipDefaultValueParams = {
  relationshipData: RelationshipType | undefined;
  objectTemplate: NodeObject | null | undefined;
  isFilterForm?: boolean;
  relationshipName?: string;
  schema?: ModelSchema | null;
  parentSchema?: ModelSchema | null;
  parentData?: NodeObject | null;
};

export const getRelationshipDefaultValue = ({
  isFilterForm,
  relationshipData,
  objectTemplate,
  relationshipName,
  schema,
  parentData,
  parentSchema,
}: GetRelationshipDefaultValueParams): FormRelationshipValue => {
  if (isFilterForm) {
    return { source: null, value: null };
  }

  if (relationshipData) {
    return getRelationshipDefaultValueFromData(relationshipData, relationshipName);
  }

  if (parentSchema && parentData && schema) {
    const relationshipToParent = schema.relationships?.find((r) => {
      return r.kind === "Parent" && r.name === relationshipName;
    });

    const relationshipFromParent = parentSchema.relationships?.find((r) => {
      return r.kind === "Component" && isOfKind(r.peer, schema);
    });

    if (relationshipToParent && relationshipFromParent) {
      return {
        source: {
          type: "user",
        },
        value: parentData,
      };
    }
  }

  return (
    getRelationshipDefaultValueFromTemplate(objectTemplate, relationshipName) ??
    DEFAULT_FORM_FIELD_VALUE
  );
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
  objectTemplate: NodeObject | null | undefined,
  relationshipName: string | undefined
): RelationshipValueFromTemplate | null => {
  if (!objectTemplate || !relationshipName) return null;

  const relationshipTemplate = objectTemplate[relationshipName] as NodeRelationship | undefined;
  if (!relationshipTemplate) return null;

  const source: TemplateSource = {
    type: "template",
    label: getNodeLabel(objectTemplate),
    kind: objectTemplate.__typename,
    id: objectTemplate.id,
  };

  if ("edges" in relationshipTemplate) {
    if (relationshipTemplate.edges.length === 0) return null;

    return {
      source,
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
  if (!node) return null;

  return {
    source,
    value: {
      id: node.id,
      display_label: getNodeLabel(node),
      __typename: node.__typename,
    },
  };
};
