import { isDeepEqual } from "remeda";

import type { DynamicFieldProps, FormFieldValue } from "@/shared/components/form/type";
import { buildFromPoolPayload } from "@/shared/components/form/utils/mutations/buildFromPoolMutationValue";
import { getAllocatedKind } from "@/shared/components/form/utils/updateFormFieldValue";

type GetUpdateMutationFromFormDataParams = {
  fields: Array<DynamicFieldProps>;
  formData: Record<string, FormFieldValue>;
};

export const getUpdateMutationFromFormData = ({
  fields,
  formData,
}: GetUpdateMutationFromFormDataParams) => {
  return fields.reduce((acc, field) => {
    const fieldData = formData[field.name];

    if (!fieldData || (field.defaultValue && isDeepEqual(fieldData, field.defaultValue))) {
      return acc;
    }

    const defaultValue = field.defaultValue;
    if (
      fieldData.source?.type === "pool" &&
      defaultValue?.source?.type === "pool" &&
      defaultValue.source.id === fieldData.source.id
    ) {
      // Re-selecting the field's original pool is normally a no-op: allocation is
      // idempotent on the reservation identifier, so the mask cannot be changed that way.
      // A different allocated kind is the exception — no reservation identifier is sent,
      // so it is a real request and must not be dropped from the mutation.
      const requestedKind =
        fieldData.value && typeof fieldData.value === "object" && "from_pool" in fieldData.value
          ? fieldData.value.from_pool.allocatedKind
          : undefined;
      if (!requestedKind || requestedKind === getAllocatedKind(defaultValue.value)) {
        return acc;
      }
    }

    const fromPoolField = field.pool?.fromPoolRelationshipName;

    switch (fieldData.source?.type) {
      case "pool": {
        if (
          fieldData.value &&
          typeof fieldData.value === "object" &&
          "from_pool" in fieldData.value
        ) {
          if (fromPoolField) {
            const clearField =
              field.type === "relationship"
                ? { [field.name]: null }
                : { [field.name]: { value: null } };
            // `<rel>_from_resource_pool` peers at the pool kind itself, so GraphQL types it
            // as a plain RelatedNodeInput — which has no `prefixlen` and no `address_type`,
            // and rejects the whole query if either is sent. The backend could not honour
            // them there anyway: the relationship stores only a pointer to the pool, and
            // `create.py` allocates with `pool.get_resource(...)`, passing no prefix length
            // and no kind. Overrides only reach the API through the direct
            // `{ [field.name]: { from_pool } }` payload below.
            return {
              ...acc,
              ...clearField,
              [fromPoolField]: { id: fieldData.value.from_pool.id },
            };
          }
          return {
            ...acc,
            [field.name]: {
              from_pool: buildFromPoolPayload(fieldData.value.from_pool, fieldData.source.kind),
            },
          };
        }
        return { ...acc, [field.name]: fieldData.value };
      }
      case "user": {
        if (fieldData.value === null) {
          if (field.type === "relationship") {
            return {
              ...acc,
              [field.name]: null,
              ...(fromPoolField ? { [fromPoolField]: null } : {}),
            };
          }
          return {
            ...acc,
            [field.name]: { value: null },
            ...(fromPoolField ? { [fromPoolField]: null } : {}),
          };
        }

        if (typeof fieldData.value === "object") {
          if (Array.isArray(fieldData.value)) {
            if (!fieldData.value.length) {
              return {
                ...acc,
                [field.name]: null,
              };
            }

            if (fieldData.value.every((value) => typeof value === "string")) {
              return {
                ...acc,
                [field.name]: { value: fieldData.value },
              };
            }

            if (fieldData.value.every((value) => "id" in value)) {
              return {
                ...acc,
                [field.name]: fieldData.value.map(({ id }) => ({ id })),
              };
            }
          }

          if ("id" in fieldData.value) {
            return {
              ...acc,
              [field.name]: { id: fieldData.value.id },
              ...(fromPoolField ? { [fromPoolField]: null } : {}),
            };
          }
        }
        return {
          ...acc,
          [field.name]: { value: fieldData.value === "" ? null : fieldData.value },
          ...(fromPoolField ? { [fromPoolField]: null } : {}),
        };
      }
      case "profile":
      case "schema": {
        return { ...acc, [field.name]: { is_default: true } };
      }
      default:
        return acc;
    }
  }, {});
};
