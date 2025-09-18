import type { ModelSchema } from "@/entities/schema/types";

export function getSchemaIcon(schema: ModelSchema | null | undefined): string {
  if (!schema?.icon) return "mdi:cube-outline";
  return schema.icon;
}
