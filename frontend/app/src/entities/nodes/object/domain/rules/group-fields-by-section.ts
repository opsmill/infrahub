import {
  ADVANCED_SECTION,
  BUILT_IN_SECTION_NAMES,
  DETAILS_SECTION,
  type FieldSection,
} from "@/entities/nodes/object/domain/model/field-section";
import type { ContainerSchema } from "@/entities/schema/domain/model/schema";

function orderContainers(containers: ContainerSchema[]): ContainerSchema[] {
  const weighted = containers
    .filter((container) => container.order_weight != null)
    .sort((a, b) => a.order_weight! - b.order_weight!);
  const unweighted = containers.filter((container) => container.order_weight == null);

  return [...weighted, ...unweighted];
}

export function groupFieldsBySection<T>(
  containers: ContainerSchema[] | null | undefined,
  items: T[],
  getContainer: (item: T) => string | null | undefined
): FieldSection<T>[] {
  const declaredContainers = orderContainers(
    (containers ?? []).filter((container) => !BUILT_IN_SECTION_NAMES.includes(container.name))
  );
  const itemsByContainer = new Map<string, T[]>();
  const declaredNames = new Set(declaredContainers.map((container) => container.name));
  const detailsItems: T[] = [];
  const advancedItems: T[] = [];

  for (const item of items) {
    const containerName = getContainer(item);

    if (containerName === ADVANCED_SECTION.name) {
      advancedItems.push(item);
    } else if (containerName && declaredNames.has(containerName)) {
      const containerItems = itemsByContainer.get(containerName) ?? [];
      containerItems.push(item);
      itemsByContainer.set(containerName, containerItems);
    } else {
      detailsItems.push(item);
    }
  }

  const sections: FieldSection<T>[] = [
    {
      key: "built-in:details",
      kind: "details",
      container: { ...DETAILS_SECTION },
      items: detailsItems,
    },
    ...declaredContainers.map((container) => ({
      key: `declared:${container.name}`,
      kind: "declared" as const,
      container,
      items: itemsByContainer.get(container.name) ?? [],
    })),
    {
      key: "built-in:advanced",
      kind: "advanced",
      container: { ...ADVANCED_SECTION },
      items: advancedItems,
    },
  ];

  return sections.filter((section) => section.items.length > 0);
}
