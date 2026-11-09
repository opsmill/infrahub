import {
  ADVANCED_SECTION,
  DETAILS_SECTION,
  type FieldSection,
} from "@/entities/nodes/object/domain/model/field-section";
import type { ContainerSchema } from "@/entities/schema/domain/model/schema";

const BUILT_IN_SECTION_NAMES: string[] = [DETAILS_SECTION.name, ADVANCED_SECTION.name];

function orderContainers(containers: ContainerSchema[]): ContainerSchema[] {
  const weightOf = (container: ContainerSchema) =>
    container.order_weight ?? Number.MAX_SAFE_INTEGER;

  return [...containers].sort((a, b) => weightOf(a) - weightOf(b));
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
    { container: DETAILS_SECTION, items: detailsItems },
    ...declaredContainers.map((container) => ({
      container,
      items: itemsByContainer.get(container.name) ?? [],
    })),
    { container: ADVANCED_SECTION, items: advancedItems },
  ];

  return sections.filter((section) => section.items.length > 0);
}
