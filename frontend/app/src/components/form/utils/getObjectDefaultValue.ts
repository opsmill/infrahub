import { AttributeType } from "@/utils/getObjectItemDisplayValue";
import { ProfileData } from "@/components/form/object-form";
import { components } from "@/infraops";

export type GetObjectDefaultValue = {
  fieldSchema: GetObjectDefaultValueFromSchema;
  initialObject?: Record<string, AttributeType>;
  profiles?: Array<ProfileData>;
  isFilterForm?: boolean;
};

export const getObjectDefaultValue = ({
  fieldSchema,
  initialObject,
  profiles = [],
  isFilterForm,
}: GetObjectDefaultValue) => {
  // Sort profiles from profile_priority value
  const orderedProfiles = profiles.sort((optionA, optionB) => {
    if (optionA.profile_priority.value < optionB.profile_priority.value) return -1;
    return 1;
  });

  // Get current object value
  const currentField = initialObject?.[fieldSchema.name];
  const currentFieldValue = currentField?.is_from_profile ? null : currentField?.value;

  // Get value from profiles depending on the priority
  const defaultValueFromProfile = orderedProfiles.find(
    (profile) => profile?.[fieldSchema.name]?.value
  )?.[fieldSchema.name]?.value;

  // Get default value from schema
  const defaultValueFromSchema = getDefaultValueFromSchema(fieldSchema);

  // Do not use profiles nor default values in filters
  if (isFilterForm) {
    return currentFieldValue ?? null;
  }

  return currentFieldValue ?? defaultValueFromProfile ?? defaultValueFromSchema ?? null;
};

export type GetObjectDefaultValueFromSchema =
  | components["schemas"]["AttributeSchema-Output"]
  | components["schemas"]["RelationshipSchema-Output"];

const getDefaultValueFromSchema = (fieldSchema: GetObjectDefaultValueFromSchema) => {
  if (fieldSchema.kind === "Boolean" || fieldSchema.kind === "Checkbox") {
    return !!fieldSchema.default_value;
  }

  return "default_value" in fieldSchema ? fieldSchema.default_value : null;
};
