import type {
  AttributeSchema,
  FieldSchema,
  RelationshipSchema,
} from "@/entities/schema/domain/model/schema";

/**
 * Describes one table surface's column rules as data. There is deliberately no surface identifier,
 * so the rules can only be read from the fields below and never branched on per surface.
 *
 * `getDefault*` must be the very functions that build this surface's columns, otherwise a column
 * can be offered that the table cannot render. `canReveal` is false wherever the fetch path has no
 * reveal seam: the candidate list then collapses to the defaults.
 */
export interface ColumnSurface {
  readonly fixedColumnIds: readonly string[];
  readonly getDefaultAttributes: (attributes: AttributeSchema[]) => AttributeSchema[];
  readonly getDefaultRelationships: (relationships: RelationshipSchema[]) => RelationshipSchema[];
  readonly excludeField: (field: FieldSchema) => boolean;
  readonly orderFields: (fields: FieldSchema[]) => FieldSchema[];
  readonly canReveal: boolean;
}
