import { LinkTab } from "@/shared/components/ui/link";

import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import { RACK_ELEVATION_TAB } from "@/entities/rack-elevation/domain/model/rack-elevation";

export interface RackElevationTabProps {
  objectKind: string;
  objectId: string;
}

export function RackElevationTab({ objectKind, objectId }: RackElevationTabProps) {
  return (
    <LinkTab
      to={getObjectDetailsUrl(objectKind, objectId, undefined, RACK_ELEVATION_TAB)}
      scrollIntoViewOnActive
    >
      Elevation
    </LinkTab>
  );
}
