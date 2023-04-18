import * as R from "ramda";
import { iNodeSchema } from "../state/atoms/schema.atom";

interface iColumn {
  label: string;
  name: string;
}

const getLabelAndName = R.pick(["label", "name"]);
const sortByLabel = R.sortBy(R.compose(R.toLower, R.prop("label")));

export const getSchemaRelationshipColumns = (
  schema: iNodeSchema
): iColumn[] => {
  if (!schema) {
    return [];
  }

  // Relationship kind to show in LIST VIEW - Attribute, Parent
  const relationships = (schema.relationships || [])
  .filter(relationship => relationship.kind === "Attribute" || relationship.kind === "Parent")
  .map(getLabelAndName);
  return sortByLabel(relationships);
};

export const getSchemaAttributeColumns = (schema: iNodeSchema): iColumn[] => {
  if (!schema) {
    return [];
  }

  const attributes = (schema.attributes || []).map(getLabelAndName);
  return sortByLabel(attributes);
};

export const getSchemaObjectColumns = (schema: iNodeSchema): iColumn[] => {
  if (!schema) {
    return [];
  }

  const attributes = getSchemaAttributeColumns(schema);
  const relationships = getSchemaRelationshipColumns(schema);

  const columns = R.concat(attributes, relationships);
  return sortByLabel(columns);
};
