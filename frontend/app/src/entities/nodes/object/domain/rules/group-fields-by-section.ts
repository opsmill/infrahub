import {
  DETAILS_SECTION,
  type FieldSection,
} from "@/entities/nodes/object/domain/model/field-section";
import type { ContainerSchema } from "@/entities/schema/domain/model/schema";

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
    (containers ?? []).filter((container) => container.name !== DETAILS_SECTION.name)
  );
  const itemsByContainer = new Map<string, T[]>();
  const declaredNames = new Set(declaredContainers.map((container) => container.name));
  const detailsItems: T[] = [];

  for (const item of items) {
    const containerName = getContainer(item);

    if (containerName && declaredNames.has(containerName)) {
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
  ];

  return sections.filter((section) => section.items.length > 0);
}
