import * as R from "remeda";

import type { NodeCore } from "@/entities/nodes/object/domain/model/node";

/** The shape GraphQL returns for a node; whether its kind exists is for the caller to check. */
export function isNodeReference(value: unknown): value is NodeCore {
  return (
    R.isPlainObject(value) &&
    typeof value.id === "string" &&
    typeof value.__typename === "string" &&
    (value.display_label == null || typeof value.display_label === "string") &&
    (value.hfid == null || Array.isArray(value.hfid))
  );
}
