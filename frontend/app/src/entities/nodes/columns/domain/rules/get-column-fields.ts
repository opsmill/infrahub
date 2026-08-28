import * as R from "remeda";

import type { ColumnSurface } from "@/entities/nodes/columns/domain/model/column-surface";
import { getAttributesVisibleInListView } from "@/entities/nodes/object/domain/rules/get-attributes-visible-in-list-view";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/domain/rules/get-relationships-visible-in-list-view";
import type {
  AttributeSchema,
  ModelSchema,
  RelationshipSchema,
} from "@/entities/schema/domain/model/schema";

type FieldSchema = AttributeSchema | RelationshipSchema;

/** One column the picker may offer, and whether the surface shows it with neither param set. */
export interface ColumnField {
  name: string;
  label: string;
  fieldSchema: FieldSchema;
  isDefaultVisible: boolean;
}

/**
 * The candidate column list for one surface, in display order.
 *
 * Candidates come from the very rule functions the surface's column builder uses, so they are
 * provably a superset of the defaults and provably renderable — the picker can never offer a
 * phantom column. A surface that cannot reveal collapses to its defaults, which is how
 * `canReveal: false` is enforced without any consumer branching on `surface.id`.
 */
export function getColumnFields(schema: ModelSchema, surface: ColumnSurface): ColumnField[] {
  const attributes = schema.attributes ?? [];
  const relationships = schema.relationships ?? [];

  const defaults: FieldSchema[] = [
    ...surface.getDefaultAttributes(attributes),
    ...surface.getDefaultRelationships(relationships),
  ];
  const defaultNames = new Set(defaults.map((field) => field.name));

  const candidates = surface.canReveal ? getRevealableFields(attributes, relationships) : defaults;

  return R.pipe(
    candidates,
    R.filter((field) => !surface.excludeField(field)),
    R.filter((field) => !surface.fixedColumnIds.includes(field.name)),
    // A field can reach this list twice — `getIpAddressRelationshipsVisibleInListView` prepends
    // `ip_prefix` on top of the generic list — and a duplicate name is a duplicate column id.
    R.uniqueBy((field) => field.name),
    (fields) => surface.orderFields(fields),
    R.map((field) => ({
      name: field.name,
      label: field.label ?? field.name,
      fieldSchema: field,
      isDefaultVisible: defaultNames.has(field.name),
    }))
  );
}

/** Every field the list view can render, with the `display: "extra"` gate fully opened. */
function getRevealableFields(
  attributes: AttributeSchema[],
  relationships: RelationshipSchema[]
): FieldSchema[] {
  const allNames = new Set([
    ...attributes.map((attribute) => attribute.name),
    ...relationships.map((relationship) => relationship.name),
  ]);

  return [
    ...getAttributesVisibleInListView(attributes, allNames),
    ...getRelationshipsVisibleInListView(relationships, allNames),
  ];
}
