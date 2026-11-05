import type { ContainerSchema } from "@/entities/schema/domain/model/schema";

export const DETAILS_SECTION = { name: "details", label: "Details", collapsed: false } as const;

export const ADVANCED_SECTION = { name: "advanced", label: "Advanced", collapsed: true } as const;

export const BUILT_IN_SECTION_NAMES: readonly string[] = [
  DETAILS_SECTION.name,
  ADVANCED_SECTION.name,
];

export type FieldSectionKind = "details" | "declared" | "advanced";

export type FieldSection<T> = {
  key: string;
  kind: FieldSectionKind;
  container: Pick<ContainerSchema, "name" | "label" | "collapsed"> &
    Partial<Pick<ContainerSchema, "description" | "order_weight">>;
  items: T[];
};
