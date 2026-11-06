import * as R from "remeda";

import type { NodeCore } from "@/entities/nodes/object/domain/model/node";
import { getSchema } from "@/entities/schema/domain/use-cases/get-schema";

/** A stored value only counts as a node when its kind exists, so a lookalike payload never links. */
export function isNodeReference(value: unknown): value is NodeCore {
  if (!R.isPlainObject(value)) return false;
  if (typeof value.id !== "string" || typeof value.__typename !== "string") return false;
  if (!(value.display_label == null || typeof value.display_label === "string")) return false;
  if (!(value.hfid == null || Array.isArray(value.hfid))) return false;

  return !!getSchema(value.__typename).schema;
}
