import { iNodeSchema } from "../state/atoms/schema.atom";

export type MutationMode = "create" | "update";

const metadataFields = ["owner", "source", "is_visible", "is_protected"];

const getMutationMetaDetailsFromFormData = (
  schema: iNodeSchema,
  data: any,
  row: any,
  type: any,
  attributeOrRelationshipName: any,
  attributeOrRelationshipToEdit: any
) => {
  const cleanedData = Object.entries(data).reduce((acc, [key, value]: [string, any]) => {
    if (!value || isNaN(value)) {
      return acc;
    }

    if (metadataFields.includes(key)) {
      return {
        ...acc,
        [`_relation__${key}`]: value,
      };
    }

    return {
      ...acc,
      [key]: value,
    };
  }, {});

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
        }

        return {
          id: item.id,
        };
      });

      return {
        id: row.id,
        [attributeOrRelationshipName]: newRelationshipList,
      };
    }

    return {
      id: row.id,
      [attributeOrRelationshipName]: {
        id: row[attributeOrRelationshipName]?.node?.id ?? row[attributeOrRelationshipName]?.id,
        ...cleanedData,
      },
    };
  }

  return {
    id: row.id,
    [attributeOrRelationshipName]: cleanedData,
  };
};

export default getMutationMetaDetailsFromFormData;
