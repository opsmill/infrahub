import * as R from "remeda";

import {
  DEFAULT_FORM_FIELD_VALUE,
  FROM_RESOURCE_POOL_SUFFIX,
} from "@/shared/components/form/constants";
import type { ProfileData } from "@/shared/components/form/object-form";
import type {
  AttributeValueFromPool,
  AttributeValueFromProfile,
  AttributeValueFromTemplate,
  AttributeValueFromUser,
  FormAttributeValue,
} from "@/shared/components/form/type";

import type { AttributeType, FieldSchema } from "@/entities/nodes/getObjectItemDisplayValue";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type {
  NodeAttributeWithMetadata,
  NodeCore,
  NodeObject,
  NodeRelationshipOneWithMetadata,
} from "@/entities/nodes/types";
import { getSchema } from "@/entities/schema/domain/get-schema";
import { isPoolSchema } from "@/entities/schema/utils/is-pool-schema";
import { isTemplateSchema } from "@/entities/schema/utils/is-template-schema";

export type GetFieldDefaultValue = {
  fieldSchema: FieldSchema;
  initialObject?: Record<string, AttributeType>;
  objectTemplate?: NodeObject | null;
  profiles?: Array<ProfileData>;
  isFilterForm?: boolean;
};

export const getFieldDefaultValue = ({
  fieldSchema,
  initialObject,
  objectTemplate,
  profiles = [],
  isFilterForm,
}: GetFieldDefaultValue): FormAttributeValue => {
  // Do not use profiles nor default values in filters
  if (isFilterForm) {
    return getCurrentFieldValue(fieldSchema.name, initialObject) ?? DEFAULT_FORM_FIELD_VALUE;
  }

  return (
    getCurrentFieldValue(fieldSchema.name, initialObject) ??
    getDefaultValueFromTemplate(fieldSchema.name, objectTemplate) ??
    getDefaultValueFromProfiles(fieldSchema.name, profiles) ??
    getDefaultValueFromPoolRelationship(fieldSchema.name, initialObject) ??
    getDefaultValueFromPool(fieldSchema.name, initialObject) ??
    getDefaultValueFromSchema(fieldSchema) ??
    DEFAULT_FORM_FIELD_VALUE
  );
};

export const getCurrentFieldValue = (
  fieldName: string,
  objectData?: Record<string, AttributeType>
): AttributeValueFromUser | AttributeValueFromPool | AttributeValueFromTemplate | null => {
  if (!objectData) return null;

  const currentField = objectData[fieldName];

  if (!currentField) return null;

  if (currentField.is_default || currentField.is_from_profile) {
    return null;
  }

  if (currentField.source && "__typename" in currentField.source) {
    const sourceKind = currentField.source.__typename as string;
    const { schema: sourceSchema } = getSchema(sourceKind);

    if (!sourceSchema) {
      return {
        source: { type: "user" },
        value: currentField.value,
      };
    }

    if (isPoolSchema(sourceSchema)) {
      return null;
    }

    if (isTemplateSchema(sourceSchema)) {
      return {
        source: {
          type: "template",
          label: getNodeLabel(currentField.source as NodeCore),
          kind: sourceKind,
          id: currentField.source.id as string,
        },
        value: currentField.value,
      };
    }

    if (sourceKind.includes("Pool")) {
      return null;
    }
  }

  return (
    getDefaultValueFromPoolRelationship(fieldName, objectData) ?? {
      source: { type: "user" },
      value: currentField.value,
    }
  );
};

const getDefaultValueFromProfiles = (
  fieldName: string,
  profiles: Array<ProfileData>
): AttributeValueFromProfile | null => {
  // Get value from profiles depending on the priority
  const orderedProfiles = R.sortBy(
    profiles,
    (profile) => profile.profile_priority?.value ?? 0,
    (profile) => profile.id
  );

  const profileWithDefaultValueForField = R.find(orderedProfiles, (profile) => {
    const profileFieldData = profile[fieldName] as
      | Pick<AttributeType, "value" | "__typename">
      | undefined;

    if (!profileFieldData) return false;
    return profileFieldData.value !== null;
  });

  if (!profileWithDefaultValueForField) return null;

  return {
    source: {
      type: "profile",
      id: profileWithDefaultValueForField.id,
      label: getNodeLabel(profileWithDefaultValueForField),
      kind: profileWithDefaultValueForField.__typename,
    },
    value: (
      profileWithDefaultValueForField[fieldName] as Pick<AttributeType, "value" | "__typename">
    ).value,
  };
};

const getDefaultValueFromPoolRelationship = (
  fieldName: string,
  objectData?: Record<string, AttributeType>
): AttributeValueFromPool | null => {
  if (!objectData) return null;

  const companionRelName = `${fieldName}${FROM_RESOURCE_POOL_SUFFIX}`;
  const companionData = objectData[companionRelName] as NodeRelationshipOneWithMetadata | undefined;

  if (!companionData?.node) return null;

  const poolNode = companionData.node;

  return {
    source: {
      type: "pool",
      id: poolNode.id,
      label: getNodeLabel(poolNode),
      kind: poolNode.__typename,
    },
    value: { from_pool: { id: poolNode.id } },
  };
};

const getDefaultValueFromPool = (
  fieldName: string,
  objectData?: Record<string, AttributeType>
): AttributeValueFromPool | null => {
  if (!objectData) return null;

  const currentField = objectData[fieldName];
  if (!currentField) return null;

  if (!currentField.source?.__typename?.match(/Pool$/g)) {
    return null;
  }

  const pool = currentField.source;

  if (!pool) return null;
  if (!pool.id) return null;

  return {
    source: {
      type: "pool",
      id: pool.id,
      label: pool.display_label || null,
      kind: pool.__typename,
    },
    value: currentField.value,
  };
};

export const getDefaultValueFromTemplate = (
  fieldName: string,
  objectTemplate?: NodeObject | null
): AttributeValueFromTemplate | AttributeValueFromPool | null => {
  if (!objectTemplate) return null;

  const currentField = objectTemplate[fieldName] as NodeAttributeWithMetadata | undefined;

  if (!currentField) return null;

  if (currentField.value === null) {
    if (currentField.source?.__typename) {
      const { schema: sourceSchema } = getSchema(currentField.source.__typename);
      if (sourceSchema && isPoolSchema(sourceSchema)) {
        return {
          source: {
            type: "pool",
            fromTemplate: true,
            id: currentField.source.id,
            label: getNodeLabel(currentField.source),
            kind: currentField.source.__typename,
          },
          value: { from_pool: { id: currentField.source.id } },
        };
      }
    }
    return null;
  }

  if (currentField.is_from_profile) return null;

  return {
    source: {
      type: "template",
      label: getNodeLabel(objectTemplate),
      kind: objectTemplate.__typename,
      id: objectTemplate.id,
    },
    value: currentField.value,
  };
};

export const getDefaultValueFromSchema = (
  fieldSchema: FieldSchema
): AttributeValueFromUser | null => {
  if (fieldSchema.kind === "Boolean" || fieldSchema.kind === "Checkbox") {
    return {
      source: typeof fieldSchema.default_value === "boolean" ? { type: "schema" } : null,
      value: !!fieldSchema.default_value,
    };
  }

  return "default_value" in fieldSchema
    ? {
        source: { type: "schema" },
        value: fieldSchema.default_value as AttributeValueFromUser["value"],
      }
    : null;
};
