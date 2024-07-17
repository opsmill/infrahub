import { FieldSchema, AttributeType } from "@/utils/getObjectItemDisplayValue";
import { ProfileData } from "@/components/form/object-form";

export type GetFieldDefaultValue = {
  fieldSchema: FieldSchema;
  initialObject?: Record<string, AttributeType>;
  profiles?: Array<ProfileData>;
  isFilterForm?: boolean;
};

export const getFieldDefaultValue = ({
  fieldSchema,
  initialObject,
  profiles = [],
  isFilterForm,
}: GetFieldDefaultValue) => {
  // Do not use profiles nor default values in filters
  if (isFilterForm) {
    return getCurrentFieldValue(fieldSchema.name, initialObject);
  }

  return (
    getCurrentFieldValue(fieldSchema.name, initialObject) ??
    getDefaultValueFromProfile(fieldSchema.name, profiles) ??
    getDefaultValueFromSchema(fieldSchema) ??
    null
  );
};

const getCurrentFieldValue = (fieldName: string, objectData?: Record<string, AttributeType>) => {
  if (!objectData) return null;

  const currentField = objectData[fieldName];
  if (!currentField) return null;

  return currentField.is_from_profile ? null : currentField.value;
};

const getDefaultValueFromProfile = (fieldName: string, profiles: Array<ProfileData>) => {
  // Get value from profiles depending on the priority
  const orderedProfiles = profiles.sort((optionA, optionB) => {
    if (optionA.profile_priority.value < optionB.profile_priority.value) return -1;
    return 1;
  });

  return orderedProfiles.find((profile) => profile?.[fieldName]?.value)?.[fieldName]?.value;
};

const getDefaultValueFromSchema = (fieldSchema: FieldSchema) => {
  if (fieldSchema.kind === "Boolean" || fieldSchema.kind === "Checkbox") {
    return !!fieldSchema.default_value;
  }

  return "default_value" in fieldSchema ? fieldSchema.default_value : null;
};
