import type {
  AttributeSchema,
  FieldSchema,
  RelationshipSchema,
} from "@/entities/schema/domain/model/schema";

/**
 * One table's column rules, as data.
 *
 * `getDefault*` must be the functions that build that table's columns, or a column can be offered
 * that the table cannot render. `canReveal: false` collapses the candidate list to the defaults.
 */
export interface ColumnSurface {
  readonly fixedColumnIds: readonly string[];
  readonly getDefaultAttributes: (attributes: AttributeSchema[]) => AttributeSchema[];
  readonly getDefaultRelationships: (relationships: RelationshipSchema[]) => RelationshipSchema[];
  readonly excludeField: (field: FieldSchema) => boolean;
  readonly orderFields: (fields: FieldSchema[]) => FieldSchema[];
  readonly canReveal: boolean;
}
