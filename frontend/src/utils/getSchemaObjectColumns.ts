import * as R from "ramda";
import { iGenericSchema, iNodeSchema } from "../state/atoms/schema.atom";

interface iColumn {
  label: string;
  name: string;
  kind?: string;
  paginated?: boolean;
}

export const getSchemaRelationshipColumns = (schema?: iNodeSchema | iGenericSchema): iColumn[] => {
  if (!schema) {
    return [];
  }

  // Relationship kind to show in LIST VIEW - Attribute, Parent
  const relationships: iColumn[] = (schema.relationships || [])
    .filter(
      (relationship) =>
        relationship.kind === "Attribute" ||
        relationship.kind === "Parent" ||
        (relationship.kind === "Component" && relationship.cardinality === "one")
    )
    .map((relationship) => ({
      label: relationship.label ?? "",
      name: relationship.name,
      paginated: relationship.cardinality === "many",
    }));

  return relationships;
};

export const getSchemaRelationshipsTabs = (schema: iNodeSchema | iGenericSchema) => {
  if (!schema) {
    return [];
  }

  // Relationship kind to show in LIST VIEW - Attribute, Parent
  const relationships = (schema.relationships || [])
    .filter((relationship) => {
      if (relationship.kind === "Generic" && relationship.cardinality === "many") {
        return true;
      }
      if (relationship.kind === "Component" && relationship.cardinality === "many") {
        return true;
      }
      return false;
    })
    .map((relationship) => ({
      label: relationship.label,
      name: relationship.name,
    }));

  return relationships;
};

export const getSchemaAttributeColumns = (schema: iNodeSchema | iGenericSchema): iColumn[] => {
  if (!schema) {
    return [];
  }

  const attributes: iColumn[] = (schema.attributes || [])
    .filter((row) => row.kind !== "HashedPassword")
    .map((row) => ({
      label: row.label ?? "",
      name: row.name,
      kind: row.kind,
    }));

  return attributes;
};

export const getSchemaObjectColumns = (schema: iNodeSchema | iGenericSchema): iColumn[] => {
  if (!schema) {
    return [];
  }

  const attributes = getSchemaAttributeColumns(schema);
  const relationships = getSchemaRelationshipColumns(schema);

  const columns = R.concat(attributes, relationships);
  return columns;
};

export const getGroupColumns = (schema: iNodeSchema | iGenericSchema): iColumn[] => {
  if (!schema) {
    return [];
  }

  const defaultColumns = [{ label: "Type", name: "__typename" }];
  const attributes = getSchemaAttributeColumns(schema);
  const relationships = getSchemaRelationshipColumns(schema);

  const columns = R.concat(attributes, relationships);

  return [...defaultColumns, ...columns];
};

export const getAttributeColumnsFromNodeOrGenericSchema = (
  schemaList: iNodeSchema[],
  generics: iGenericSchema[],
  kind: String
): iColumn[] => {
  const generic = generics.find((g) => g.kind === kind);
  const peerSchema = schemaList.find((s) => s.kind === kind);
  if (generic) {
    return getSchemaAttributeColumns(generic);
  }
  if (peerSchema) {
    return getSchemaAttributeColumns(peerSchema);
  }
  return [];
};
