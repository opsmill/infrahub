import * as R from "ramda";
import { iNodeSchema } from "../state/atoms/schema.atom";

export type MutationMode = "create" | "update";

const getMutationDetailsFromFormData = (
  schema: iNodeSchema,
  formData: any,
  mode: MutationMode,
  existingObject?: any
) => {
  const updateObject = R.clone(formData);

  schema.attributes?.forEach((attribute) => {
    const updatedValue = updateObject[attribute.name].value;
    if (mode === "update") {
      const existingValue = existingObject[attribute.name].value;
      if (mode === "update" && (!updatedValue || updatedValue === existingValue))
        delete updateObject[attribute.name];
    }
  });

  schema.relationships?.filter((relationship) => relationship.kind === "Attribute").forEach((relationship) => {
    const isOneToOne =
      relationship.kind === "Attribute" && relationship.cardinality === "one";

    const isOneToMany =
      relationship.kind === "Attribute" && relationship.cardinality === "many";

    if (mode === "update") {
      if (isOneToOne) {
        const existingValue = existingObject[relationship.name].id;
        const updatedValue = updateObject[relationship.name].id;
        if (updatedValue === existingValue) {
          delete updateObject[relationship.name];
        }
      } else {
        const existingValue = existingObject[relationship.name].map((r: any) => r.id).sort();
        const updatedIds = updateObject[relationship.name].map((value: any) => value.value).sort();
        if (JSON.stringify(updatedIds) === JSON.stringify(existingValue)) {
          delete updateObject[relationship.name];
        }
      }
    }

    if(isOneToMany) {
      updateObject[relationship.name] = updateObject[relationship.name].map((row: any) => ({ id: row.value }));
    }
  });

  return updateObject;
};

export default getMutationDetailsFromFormData;
