import { iNodeSchema } from "../state/atoms/schema.atom";

export type MutationMode = "create" | "update";

const getMutationDetailsFromFormData = (
  schema: iNodeSchema,
  formData: any,
  mode: MutationMode,
  existingObject?: any
) => {
  const mutationArgs: any[] = [];

  schema.attributes?.forEach((attribute) => {
    const updatedValue = formData[attribute.name];
    if (mode === "update") {
      const existingValue = existingObject[attribute.name].value;
      if (mode === "update" && (!updatedValue || updatedValue === existingValue))
        return false;
    }

    if (attribute.kind === "String") {
      mutationArgs.push(`\n\t${attribute.name}: { value: "${updatedValue}" }`);
    } else {
      mutationArgs.push(`\n\t${attribute.name}: { value: ${updatedValue} }`);
    }
  });

  schema.relationships?.forEach((relationship) => {
    const updatedValue = formData[relationship.name];
    if (!updatedValue) return false;

    const isOneToOne =
      relationship.kind === "Attribute" && relationship.cardinality === "one";
    const isOneToMany =
      relationship.kind === "Attribute" && relationship.cardinality === "many";

    let existingValue;
    if (mode === "update") {
      if (isOneToOne) {
        existingValue = existingObject[relationship.name].id;
        if (updatedValue === existingValue) {
          return false;
        }
      } else {
        existingValue = existingObject[relationship.name].map((r: any) => r.id);
        const updatedIds = updatedValue.map((value: any) => value.value).sort();
        if (JSON.stringify(updatedIds) === JSON.stringify(existingValue)) {
          return false;
        }
      }
    }

    if (isOneToOne) {
      mutationArgs.push(`\n\t${relationship.name}: { id: "${updatedValue}" }`);
    } else if (isOneToMany) {
      const values = updatedValue
      .map((value: any) => `{ id: "${value.value}" }`)
      .join(",");
      mutationArgs.push(`\n\t${relationship.name}: [${values}]`);
    }
  });

  return mutationArgs;
};

export default getMutationDetailsFromFormData;
