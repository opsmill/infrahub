import type { ContainerSchema } from "@/entities/schema/domain/model/schema";

export const DETAILS_SECTION = {
  name: "details",
  label: "Details",
  collapsible: false,
  collapsed: false,
} as const;

export const DETAILS_SECTION_ORDER_WEIGHT = 0;

export type FieldSection<T> = {
  container: Pick<ContainerSchema, "name" | "label" | "collapsible" | "collapsed"> &
    Partial<Pick<ContainerSchema, "description" | "order_weight">>;
  items: T[];
};
