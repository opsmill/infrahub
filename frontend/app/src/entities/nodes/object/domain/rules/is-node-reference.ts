import * as R from "remeda";

import type { NodeCore } from "@/entities/nodes/object/domain/model/node";

/** An element shaped like a GraphQL node: an object with a string `id` and a string `__typename`. */
export function isNodeReference(value: unknown): value is NodeCore {
  return (
    R.isPlainObject(value) && typeof value.id === "string" && typeof value.__typename === "string"
  );
}
