import {
  type RackElevationKind,
  RackElevationRole,
} from "@/entities/rack-elevation/domain/model/rack-elevation";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { isGenericSchema } from "@/entities/schema/domain/rules/is-generic-schema";

export const isRackKind = (schema: ModelSchema, kinds: RackElevationKind[]) => {
  const rackKinds = new Set(
    kinds.filter(({ role }) => role === RackElevationRole.RACK).map(({ kind }) => kind)
  );
  if (rackKinds.size === 0) return false;

  if (schema.kind && rackKinds.has(schema.kind)) return true;
  if (isGenericSchema(schema)) return false;

  return (schema.inherit_from ?? []).some((kind) => rackKinds.has(kind));
};
