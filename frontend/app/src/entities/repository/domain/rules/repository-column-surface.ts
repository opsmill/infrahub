import type { ColumnSurface } from "@/entities/nodes/columns/domain/model/column-surface";
import { OBJECT_COLUMN_SURFACE } from "@/entities/nodes/columns/domain/rules/column-surfaces";
import { isPushStateAttribute } from "@/entities/repository/domain/rules/is-push-state-attribute";

export const REPOSITORY_COLUMN_SURFACE: ColumnSurface = {
  ...OBJECT_COLUMN_SURFACE,
  excludeField: (field) =>
    OBJECT_COLUMN_SURFACE.excludeField(field) || isPushStateAttribute(field.name),
};
