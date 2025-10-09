import type {
  DynamicFieldProps,
  FormAttributeValue,
  FormFieldValue,
} from "@/shared/components/form/type";

import type { ConvertFormFieldValue } from "@/entities/nodes/convert/types";

export type FieldMappingData =
  | { source_field: string }
  | { data: { peer_ids: Array<string> } }
  | { data: { peer_id: string } }
  | { data: { attribute_value: FormAttributeValue["value"] } }
  | { use_default_value: boolean };

export function getFieldsMappingPayload(
  fields: DynamicFieldProps[],
  formData: {
    [key: string]: FormFieldValue | ConvertFormFieldValue;
  }
): Record<string, FieldMappingData> {
  return fields.reduce((acc, field) => {
    const fieldData = formData[field.name];

    if (!fieldData || !fieldData?.source) {
      return {
        ...acc,
        [field.name]: {
          use_default_value: true,
        },
      };
    }

    // Map source field from source object
    if (fieldData.source?.type === "source") {
      return {
        ...acc,
        [field.name]: {
          source_field: fieldData.source.name,
        },
      };
    }

    // Map array values for relationship fields (excluding List type attributes)
    if (field.type === "relationship") {
      if (field.relationship.cardinality === "many") {
        return {
          ...acc,
          [field.name]: {
            data: { peer_ids: fieldData.value },
          },
        };
      }

      if (field.relationship.cardinality === "one") {
        return {
          ...acc,
          [field.name]: {
            data: { peer_id: fieldData.value },
          },
        };
      }
    }

    if (fieldData.value !== undefined) {
      return {
        ...acc,
        [field.name]: {
          data: { attribute_value: fieldData.value },
        },
      };
    }

    // Use default value when no data is provided
    return {
      ...acc,
      [field.name]: {
        use_default_value: true,
      },
    };
  }, {});
}
