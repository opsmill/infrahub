import type { Sort } from "@/entities/nodes/sort/domain/model/sort";
import { parseSortToken } from "@/entities/nodes/sort/domain/rules/sort-token";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

export function getSchemaDefaultSort(schema: ModelSchema): Array<Sort> | null {
  if (!schema.order_by || schema.order_by.length === 0) {
    return null;
  }

  return schema.order_by.map(parseSortToken);
}
