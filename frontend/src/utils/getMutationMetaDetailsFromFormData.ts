import { iNodeSchema } from "../state/atoms/schema.atom";

export type MutationMode = "create" | "update";

const getMutationMetaDetailsFromFormData = (
  schema: iNodeSchema,
  data: any,
  row: any,
  type: any,
  attributeOrRelationshipName: any,
  attributeOrRelationshipToEdit: any
) => {
  let updatedObject: any = {
    id: row.id,
  };

  let cleanedData = Object.entries(data).reduce(
    (acc, [key, value]) => (value !== undefined && value !== "" ? { ...acc, [key]: value } : acc),
    {}
  );

  if (type === "relationship") {
    const relationshipSchema = schema.relationships?.find(
      (s) => s.name === attributeOrRelationshipName
    );

    if (relationshipSchema?.cardinality === "many") {
      const newRelationshipList = row[attributeOrRelationshipName].map((item: any) => {
        if (
          item?.node?.id === attributeOrRelationshipToEdit.id ||
          item?.id === attributeOrRelationshipToEdit.id
        ) {
          return {
            ...cleanedData,
            id: item.id,
          };
        } else {
          return {
            id: item.id,
          };
        }
      });

      updatedObject[attributeOrRelationshipName] = newRelationshipList;
    } else {
      updatedObject[attributeOrRelationshipName] = {
        id: row[attributeOrRelationshipName]?.node?.id ?? row[attributeOrRelationshipName]?.id,
        ...cleanedData,
      };
    }
  } else {
    updatedObject[attributeOrRelationshipName] = {
      ...cleanedData,
    };
  }

  return updatedObject;
};

export default getMutationMetaDetailsFromFormData;
