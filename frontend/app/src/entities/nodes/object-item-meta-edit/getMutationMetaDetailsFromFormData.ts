import type { NodeSchema } from "@/entities/schema/types";

const metadataFields = ["source", "owner", "is_protected"];

const isValueValid = (value: any) => {
  if (value === undefined) {
    // Value should not be undefined
    return false;
  }

  if (typeof value === "string") {
    // Verify empty string
    return !!value;
  }

  // Verify number
  return !isNaN(value);
};

const getMutationMetaDetailsFromFormData = (
  schema: NodeSchema,
  data: any,
  row: any,
  type: any,
  attributeOrRelationshipName: any,
  attributeOrRelationshipToEdit: any
) => {
  const cleanedData = Object.entries(data).reduce((acc, [key, value]: [string, any]) => {
    if (!isValueValid(value?.id || value) || !metadataFields.includes(key)) {
      return acc;
    }

    if (type === "relationship") {
      return {
        ...acc,
        [`_relation__${key}`]: value?.id || value,
      };
    }

    return {
      ...acc,
      [key]: value?.id || value,
    };
  }, {});

  if (type === "relationship") {
    const relationshipSchema = schema.relationships?.find(
      (s) => s.name === attributeOrRelationshipName
    );

    if (relationshipSchema?.cardinality === "many") {
      const newRelationshipList = row[attributeOrRelationshipName].map((item: any) => {
        if (item?.node?.id === attributeOrRelationshipToEdit.id) {
          return {
            ...cleanedData,
            id: item.node?.id,
          };
        }

        return {
          id: item.node?.id,
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
