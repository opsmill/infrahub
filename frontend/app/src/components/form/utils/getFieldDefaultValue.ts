import { FieldSchema, AttributeType } from "@/utils/getObjectItemDisplayValue";
import { ProfileData } from "@/components/form/object-form";
import { FormAttributeValue } from "@/components/form/type";
import * as R from "ramda";

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
}: GetFieldDefaultValue): FormAttributeValue => {
  // Do not use profiles nor default values in filters
  if (isFilterForm) {
    return getCurrentFieldValue(fieldSchema.name, initialObject) ?? { source: null, value: null };
  }

  return (
    getCurrentFieldValue(fieldSchema.name, initialObject) ??
    getDefaultValueFromProfiles(fieldSchema.name, profiles) ??
    getDefaultValueFromSchema(fieldSchema) ?? { source: null, value: null }
  );
};

const getCurrentFieldValue = (
  fieldName: string,
  objectData?: Record<string, AttributeType>
): FormAttributeValue | null => {
  if (!objectData) return null;

  const currentField = objectData[fieldName];
  if (!currentField) return null;

  return currentField.is_from_profile
    ? null
    : { source: { type: "user" }, value: currentField.value };
};

const getDefaultValueFromProfiles = (
  fieldName: string,
  profiles: Array<ProfileData>
): FormAttributeValue | null => {
  // Get value from profiles depending on the priority
  const orderedProfiles = R.sortWith<ProfileData>([
    R.ascend(R.path(["profile_priority", "value"])),
    R.ascend(R.prop("id")),
  ])(profiles);

  const profileWithDefaultValueForField = orderedProfiles.find((profile) => profile?.[fieldName]);
  if (!profileWithDefaultValueForField) return null;

  return {
    source: {
      type: "profile",
      id: profileWithDefaultValueForField.id,
      label: profileWithDefaultValueForField.display_label,
      kind: profileWithDefaultValueForField.__typename,
    },
    value: profileWithDefaultValueForField[fieldName].value,
  };
};

const getDefaultValueFromSchema = (fieldSchema: FieldSchema): FormAttributeValue | null => {
  if (fieldSchema.kind === "Boolean" || fieldSchema.kind === "Checkbox") {
    return {
      source: typeof fieldSchema.default_value === "boolean" ? { type: "schema" } : null,
      value: !!fieldSchema.default_value,
    };
  }

  return "default_value" in fieldSchema
    ? {
        source: { type: "schema" },
        value: fieldSchema.default_value as FormAttributeValue["value"],
      }
    : null;
};
