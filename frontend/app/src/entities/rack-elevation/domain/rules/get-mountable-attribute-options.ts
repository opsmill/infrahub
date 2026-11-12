import {
  type RackElevationKind,
  RackElevationRole,
  type RackItemAttributeOption,
  type RackItemAttributeOptions,
} from "@/entities/rack-elevation/domain/model/rack-elevation";
import { ATTRIBUTE_KIND } from "@/entities/schema/domain/model/attribute-kind";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

export interface GetMountableAttributeOptionsParams {
  kinds: RackElevationKind[];
  schemas: ModelSchema[];
}

export const getMountableAttributeOptions = ({
  kinds,
  schemas,
}: GetMountableAttributeOptionsParams): RackItemAttributeOptions => {
  const mountableKinds = new Set(
    kinds.filter(({ role }) => role === RackElevationRole.MOUNTABLE).map(({ kind }) => kind)
  );

  const labelBy = new Map<string, RackItemAttributeOption>();
  const colorBy = new Map<string, RackItemAttributeOption>();

  for (const schema of schemas) {
    if (!schema.kind || !mountableKinds.has(schema.kind)) continue;

    for (const attribute of schema.attributes ?? []) {
      const option = { name: attribute.name, label: attribute.label ?? attribute.name };
      labelBy.set(attribute.name, option);
      if (attribute.kind === ATTRIBUTE_KIND.DROPDOWN) colorBy.set(attribute.name, option);
    }
  }

  return { labelBy: [...labelBy.values()], colorBy: [...colorBy.values()] };
};
