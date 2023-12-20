import * as R from "ramda";
import { iNodeSchema } from "../state/atoms/schema.atom";

export type MutationMode = "create" | "update";

const getMutationDetailsFromFormData = (
  schema: iNodeSchema | undefined,
  formData: any,
  mode: MutationMode,
  existingObject?: any
) => {
  if (!schema) return;

  const updatedObject = R.clone(formData);

  schema.attributes?.forEach((attribute) => {
    const updatedValue = updatedObject[attribute.name]?.value ?? attribute?.default_value;

    if (attribute.read_only) {
      // Delete the attribute if it's read-only
      delete updatedObject[attribute.name];
    }

    if (mode === "update" && existingObject) {
      const existingValue = existingObject[attribute.name]?.value;

      if (mode === "update" && updatedValue === existingValue) {
        delete updatedObject[attribute.name];
      }

      if (mode === "update" && !updatedValue && !existingValue) {
        delete updatedObject[attribute.name];
      }
    }

    if (mode === "create" && (updatedValue === null || updatedValue === "")) {
      delete updatedObject[attribute.name];
    }
  });

  schema?.relationships?.forEach((relationship) => {
    const isOneToOne = relationship.cardinality === "one";

    const isOneToMany = relationship.cardinality === "many";

    if (mode === "update" && existingObject) {
      if (isOneToOne) {
        const existingValue = existingObject[relationship.name]?.id;

        const updatedValue = updatedObject[relationship.name]?.id;

        if (updatedValue === existingValue) {
          delete updatedObject[relationship.name];
        }

        if (!updatedValue && !existingValue) {
          delete updatedObject[relationship.name];
        }
      } else {
        const existingValue = existingObject[relationship.name]?.edges
          .map((r: any) => r.node?.id)
          .sort();

        const updatedIds = updatedObject[relationship.name]?.list
          ?.map((value: any) => value.id)
          .sort();

        if (
          existingValue &&
          updatedIds &&
          JSON.stringify(updatedIds) === JSON.stringify(existingValue)
        ) {
          delete updatedObject[relationship.name];
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
      delete updatedObject[relationship.name];
    }

    if (isOneToMany && updatedObject[relationship.name] && updatedObject[relationship.name].list) {
      const fieldKeys = Object.keys(updatedObject[relationship.name]).filter(
        (key) => key !== "list"
      );

      updatedObject[relationship.name] = updatedObject[relationship.name].list.map((row: any) => {
        const objWithMetaFields: any = {
          id: row.id,
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
