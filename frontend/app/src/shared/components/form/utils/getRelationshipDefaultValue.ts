import * as R from "remeda";

import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import type { ProfileData } from "@/shared/components/form/object-form";
import type {
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
  objectTemplate: NodeObject | null | undefined;
  profiles?: Array<ProfileData>;
  isFilterForm?: boolean;
  relationshipName: string;
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

  return (
    getRelationshipValueFromUser(relationshipData, relationshipName) ??
    getRelationshipValueFromParent(schema, parentSchema, parentData, relationshipName) ??
    getRelationshipDefaultValueFromTemplate(objectTemplate, relationshipName) ??
    getRelationshipDefaultValueFromProfiles(relationshipName, profiles) ??
    DEFAULT_FORM_FIELD_VALUE
  );
};

const getRelationshipValueFromUser = (
  relationshipData: RelationshipType | undefined,
  peerField: string
): RelationshipValueFromUser | RelationshipValueFromPool | null => {
  if (!relationshipData) return null;

  if ("edges" in relationshipData) {
    if (relationshipData.edges.length === 0) return null;

    // Check if all edges come from a profile source - if so, return null to allow profile fallback
    const edgesWithSource = relationshipData.edges.filter(
      (edge) => edge.properties?.source?.__typename
    );

    if (edgesWithSource.length > 0 && edgesWithSource.length === relationshipData.edges.length) {
      const allFromProfile = edgesWithSource.every((edge) => {
        const { isProfile } = getSchema(edge.properties?.source?.__typename);
        return isProfile;
      });

      if (allFromProfile) return null;
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

    return {
      source: { type: "user" },
      value: values,
    };
  }

  // Cardinality one
  if (!relationshipData.node) return null;

  const source = relationshipData.properties?.source;
  if (!source?.__typename) {
    return {
      source: { type: "user" },
      value: relationshipData.node,
    };
  }

  const { schema: sourceSchema, isProfile, isGeneric } = getSchema(source.__typename);

  // Return null for profile sources to allow profile fallback
  if (isProfile) return null;

  // Handle pool sources
  if (!isGeneric && sourceSchema && sourceSchema.inherit_from?.includes(RESOURCE_GENERIC_KIND)) {
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
    source: { type: "user" },
    value: relationshipData.node,
  };
};

const getRelationshipValueFromParent = (
  schema: ModelSchema | null | undefined,
  parentSchema: ModelSchema | null | undefined,
  parentData: NodeObject | null | undefined,
  relationshipName: string | undefined
): RelationshipValueFromUser | null => {
  if (!parentSchema || !parentData || !schema) return null;

  const relationshipToParent = schema.relationships?.find((r) => {
    return r.kind === "Parent" && r.name === relationshipName;
  });

  const relationshipFromParent = parentSchema.relationships?.find((r) => {
    return r.kind === "Component" && isOfKind(r.peer, schema);
  });

  if (relationshipToParent && relationshipFromParent) {
    return {
      source: { type: "user" },
      value: {
        id: parentData.id,
        display_label: getNodeLabel(parentData),
        __typename: parentData.__typename,
      },
    };
  }

  return null;
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
    label: profileWithDefaultValueForField.display_label ?? null,
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
