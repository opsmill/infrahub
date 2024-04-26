import * as R from "ramda";
import { SCHEMA_ATTRIBUTE_KIND } from "../config/constants";
import { iNodeSchema } from "../state/atoms/schema.atom";

export type MutationMode = "create" | "update";

// TODO: refactor this important function for better maintenance
const getMutationDetailsFromFormData = (
  schema: iNodeSchema | undefined,
  formData: any,
  mode: MutationMode,
  existingObject?: any,
  profile?: any
) => {
  if (!schema) return;

  const updatedObject = R.clone(formData);

  schema.attributes?.forEach((attribute) => {
    const updatedValue =
      updatedObject[attribute.name]?.value?.id ??
      updatedObject[attribute.name]?.value ??
      attribute?.default_value;

    const profileValue =
      profile && (profile[attribute.name]?.value?.id ?? profile[attribute.name]?.value);

    if (attribute.read_only) {
      // Delete the attribute if it's read-only
      delete updatedObject[attribute.name];
    }

    if (mode === "update" && existingObject) {
      const existingValue = existingObject[attribute.name]?.value;

      if (existingValue && !updatedValue && attribute.kind === SCHEMA_ATTRIBUTE_KIND.DROPDOWN) {
        // Set as null for dropdown attributes
        updatedObject[attribute.name] = { value: null };
        return;
      }

      if (JSON.stringify(updatedValue) === JSON.stringify(existingValue)) {
        delete updatedObject[attribute.name];
      }

      if (!updatedValue && !existingValue) {
        // Remove property if it's empty
        delete updatedObject[attribute.name];
      }

      if (updatedValue === profileValue) {
        // Remove property if it comes from the profile
        delete updatedObject[attribute.name];
      }
    }

    if (
      mode === "create" &&
      (updatedValue === null || updatedValue === "" || updatedValue === profileValue)
    ) {
      // Remove property if it's empty or comes from the profile
      delete updatedObject[attribute.name];
    }
  });

  schema?.relationships?.forEach((relationship) => {
    const isOneToOne = relationship.cardinality === "one";

    const isOneToMany = relationship.cardinality === "many";

    if (mode === "update" && existingObject) {
      if (isOneToOne) {
        const existingValue = existingObject[relationship.name]?.node?.id;

        const updatedValue = updatedObject[relationship.name]?.id;

        if (updatedValue === existingValue) {
          delete updatedObject[relationship.name];
          return;
        }

        if (!updatedValue && !existingValue) {
          delete updatedObject[relationship.name];
          return;
        }
      } else {
        const existingValue = existingObject[relationship.name]?.edges
          .map((r: any) => r.node?.id)
          .sort();

        const updatedIds = updatedObject[relationship.name]?.list?.sort() ?? [];

        if (JSON.stringify(updatedIds) === JSON.stringify(existingValue)) {
          delete updatedObject[relationship.name];
          return;
        }
      }
    }

    if (mode === "create") {
      if (isOneToOne) {
        if (!updatedObject[relationship.name]) {
          delete updatedObject[relationship.name];
        }
      }

      if (isOneToMany) {
        if (!updatedObject[relationship.name]?.list?.length) {
          delete updatedObject[relationship.name];
        }
      }
    }

    if (isOneToOne && updatedObject[relationship.name] && !updatedObject[relationship.name].id) {
      // Set to null to remove the relationship
      updatedObject[relationship.name] = null;
      return;
    }

    if (isOneToMany && updatedObject[relationship.name] && updatedObject[relationship.name].list) {
      const fieldKeys = Object.keys(updatedObject[relationship.name]).filter(
        (key) => key !== "list"
      );

      updatedObject[relationship.name] = updatedObject[relationship.name].list.map((id: string) => {
        const objWithMetaFields: any = {
          id,
        };

        fieldKeys.forEach((key) => {
          objWithMetaFields[key] = updatedObject[relationship.name][key];
        });

        return objWithMetaFields;
      });
    }
  });

  return updatedObject;
};

export default getMutationDetailsFromFormData;
