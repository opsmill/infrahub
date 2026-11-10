// PROTOTYPE design-jam schema-viewer-sections
// Section grouping from rev 3, after the built-in Advanced section was dropped; later revisions copy it.
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

import { type Source, sectionSource, type ViewerSection } from "./context";

const byWeight = <T extends { order_weight?: number | null }>(items: T[]) =>
  [...items].sort((a, b) => (a.order_weight ?? 0) - (b.order_weight ?? 0));

/** No built-in Advanced section: a field whose container is not declared stays in Details. */
export function viewerSectionsRev03(schema: ModelSchema): ViewerSection[] {
  const containers = "containers" in schema ? (schema.containers ?? []) : [];
  const attributes = byWeight(schema.attributes ?? []);
  const relationships = byWeight(schema.relationships ?? []);
  if (containers.length === 0) return [];

  const declared = byWeight(containers).map((c) => c.name);
  const sectionOf = (f: { container?: string | null }) =>
    declared.includes(f.container ?? "") ? f.container! : "details";
  const make = (
    name: string,
    label: string,
    rest: Partial<ViewerSection> & { source: Source }
  ): ViewerSection => ({
    name,
    label,
    collapsed: false,
    attributes: attributes.filter((f) => sectionOf(f) === name),
    relationships: relationships.filter((f) => sectionOf(f) === name),
    ...rest,
  });

  const sections = [
    make("details", "Details", { source: { type: "builtin" } }),
    ...byWeight(containers).map((c) =>
      make(c.name, c.label ?? c.name, {
        description: c.description,
        collapsed: !!c.collapsed,
        orderWeight: c.order_weight,
        source: sectionSource(schema, c),
      })
    ),
  ];
  return sections.filter(
    (s) => s.source.type !== "builtin" || s.attributes.length > 0 || s.relationships.length > 0
  );
}
