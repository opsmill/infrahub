import * as R from "remeda";

import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import type { ProfileData } from "@/shared/components/form/object-form";
import type {
  EmptyFieldValue,
  FormRelationshipValue,
  RelationshipValueFromPool,
  RelationshipValueFromProfile,
  RelationshipValueFromTemplate,
  RelationshipValueFromUser,
  TemplateSource,
} from "@/shared/components/form/type";

import type { RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { NodeObject, NodeRelationship } from "@/entities/nodes/types";
import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/constants";
import { getSchema } from "@/entities/schema/domain/get-schema";
import type { ModelSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

type GetRelationshipDefaultValueParams = {
  relationshipData: RelationshipType | undefined;
  objectTemplate?: NodeObject | null | undefined;
  profiles?: Array<ProfileData>;
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
  profiles = [],
  relationshipName,
  schema,
  parentData,
  parentSchema,
}: GetRelationshipDefaultValueParams): FormRelationshipValue => {
  if (isFilterForm) {
    return { source: null, value: null };
  }

  if (relationshipData) {
    const valueFromData = getRelationshipDefaultValueFromData(relationshipData, relationshipName);
    if (valueFromData !== null) {
      return valueFromData;
    }
    // If valueFromData is null (empty edges or null node), fall through to template/profile fallback
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
    getRelationshipDefaultValueFromProfiles(relationshipName, profiles) ??
    DEFAULT_FORM_FIELD_VALUE
  );
};

export const getRelationshipDefaultValueFromData = (
  relationshipData: RelationshipType,
  peerField?: string
):
  | RelationshipValueFromUser
  | RelationshipValueFromPool
  | RelationshipValueFromProfile
  | EmptyFieldValue
  | null => {
  if ("edges" in relationshipData) {
    // If edges are empty, return null to allow profile fallback
    if (relationshipData.edges.length === 0) {
      return null;
    }

    const values = relationshipData.edges
      .map(({ node }) =>
        node
          ? {
              id: node.id,
              display_label: node.display_label,
              __typename: node.__typename,
              ...(peerField && (node as Record<string, unknown>)[peerField] !== undefined
                ? { [peerField]: (node as Record<string, unknown>)[peerField] }
                : {}),
            }
          : null
      )
      .filter((n) => !!n);

    // Check if all edges have a profile source
    const edgesWithSource = relationshipData.edges.filter(
      (edge) => edge.properties?.source?.__typename
    );

    if (edgesWithSource.length > 0 && edgesWithSource.length === relationshipData.edges.length) {
      // All edges have a source - check if they're all from profiles
      const allFromProfile = edgesWithSource.every((edge) => {
        const { isProfile } = getSchema(edge.properties?.source?.__typename);
        return isProfile;
      });

      if (allFromProfile) {
        // Use the first edge's source as the profile source
        const firstEdgeSource = edgesWithSource[0]?.properties?.source;
        if (firstEdgeSource?.__typename) {
          return {
            source: {
              type: "profile",
              label: firstEdgeSource.display_label ?? null,
              id: firstEdgeSource.id as string,
              kind: firstEdgeSource.__typename,
            },
            value: values,
          };
        }
      }
    }

    return {
      source: {
        type: "user",
      },
      value: values,
    };
  }

  // If node is null, return null to allow profile fallback
  if (!relationshipData.node) {
    return null;
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
  const { schema: sourceSchema, isProfile, isGeneric } = getSchema(source.__typename);

  if (!isGeneric && sourceSchema && sourceSchema.inherit_from?.includes(RESOURCE_GENERIC_KIND)) {
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

  if (isProfile) {
    return {
      source: {
        type: "profile",
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

type ProfileRelationshipNode = {
  id: string;
  display_label: string;
  __typename: string;
};

type ProfileRelationshipOneData = {
  node: ProfileRelationshipNode | null;
};

type ProfileRelationshipManyData = {
  edges: Array<{ node: ProfileRelationshipNode | null }>;
};

type ProfileRelationshipData = ProfileRelationshipOneData | ProfileRelationshipManyData;

const isRelationshipManyData = (
  data: ProfileRelationshipData
): data is ProfileRelationshipManyData => {
  return "edges" in data;
};

const hasRelationshipValue = (data: ProfileRelationshipData): boolean => {
  if (isRelationshipManyData(data)) {
    return data.edges.length > 0 && data.edges.some((edge) => edge.node !== null);
  }
  return data.node !== null;
};

export const getRelationshipDefaultValueFromProfiles = (
  relationshipName: string | undefined,
  profiles: Array<ProfileData>
): RelationshipValueFromProfile | null => {
  if (!relationshipName) return null;

  // Get value from profiles depending on the priority
  const orderedProfiles = R.sortBy(
    profiles,
    (profile) => profile.profile_priority?.value ?? 0,
    (profile) => profile.id
  );

  const profileWithDefaultValueForField = R.find(orderedProfiles, (profile) => {
    const profileRelationshipData = profile[relationshipName] as
      | ProfileRelationshipData
      | undefined;
    if (!profileRelationshipData) return false;
    return hasRelationshipValue(profileRelationshipData);
  });

  if (!profileWithDefaultValueForField) return null;

  const relationshipData = profileWithDefaultValueForField[
    relationshipName
  ] as ProfileRelationshipData;

  const source = {
    type: "profile" as const,
    id: profileWithDefaultValueForField.id,
    label: profileWithDefaultValueForField.display_label,
    kind: profileWithDefaultValueForField.__typename,
  };

  // Handle cardinality many relationships
  if (isRelationshipManyData(relationshipData)) {
    const nodes = relationshipData.edges
      .map(({ node }) =>
        node
          ? {
              id: node.id,
              display_label: node.display_label,
              __typename: node.__typename,
            }
          : null
      )
      .filter((n): n is ProfileRelationshipNode => n !== null);

    return {
      source,
      value: nodes,
    };
  }

  // Handle cardinality one relationships
  if (!relationshipData.node) return null;

  return {
    source,
    value: {
      id: relationshipData.node.id,
      display_label: relationshipData.node.display_label,
      __typename: relationshipData.node.__typename,
    },
  };
};
