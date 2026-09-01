import type {
  AttributeSchema,
  FieldSchema,
  RelationshipSchema,
} from "@/entities/schema/domain/model/schema";

/**
 * Describes one table surface's column rules as data. There is deliberately no surface identifier:
 * with nothing to branch on, a consumer *cannot* grow an `if (surface === "ipam")` — the rules can
 * only be read from the fields below.
 *
 * `getDefault*` must be the very functions that surface's column builder calls, otherwise the
 * picker can offer a column the table cannot render. `canReveal` is false wherever the fetch path
 * has no reveal seam: the candidate list then collapses to the defaults.
 *
 * The vocabulary lives here; the four concrete surfaces live in `domain/rules/column-surfaces`.
 * Naming a surface means naming the rule functions it composes, and `domain/model` is a pure leaf
 * that may not reach into `domain/rules`.
 */
export interface ColumnSurface {
  readonly fixedColumnIds: readonly string[];
  readonly getDefaultAttributes: (attributes: AttributeSchema[]) => AttributeSchema[];
  readonly getDefaultRelationships: (relationships: RelationshipSchema[]) => RelationshipSchema[];
  readonly excludeField: (field: FieldSchema) => boolean;
  readonly orderFields: (fields: FieldSchema[]) => FieldSchema[];
  readonly canReveal: boolean;
}
