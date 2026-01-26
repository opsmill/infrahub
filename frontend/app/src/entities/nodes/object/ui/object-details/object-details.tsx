import { useQueryState } from "nuqs";

import { Col } from "@/shared/components/container";
import { QSP } from "@/shared/config/qsp";
import { useTitle } from "@/shared/hooks/useTitle";

import { ObjectActivitiesCard } from "@/entities/nodes/object/ui/object-details/object-activities-card";
import { ObjectDetailsCard } from "@/entities/nodes/object/ui/object-details/object-details-card";
import { ObjectProfilesGroupsCard } from "@/entities/nodes/object/ui/object-details/object-profiles-groups-card";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { ObjectDetailsTabContent } from "@/entities/nodes/relationships/ui/object-details-tab-content";
import type { NodeObjectWithMetadata } from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";

interface ObjectDetailsProps {
  objectSchema: ModelSchema;
  objectData: NodeObjectWithMetadata;
  permission: Permission;
}

export function ObjectDetails({ objectSchema, objectData, permission }: ObjectDetailsProps) {
  const [qspTab] = useQueryState(QSP.TAB);
  useTitle(`${getNodeLabel(objectData)} details`);

  if (qspTab) {
    return (
      <ObjectDetailsTabContent
        objectSchema={objectSchema}
        objectDetailsData={objectData}
        permission={permission}
      />
    );
  }

  return (
    <div className="flex flex-col gap-2 overflow-auto p-2 xl:grid xl:grid-cols-3 xl:items-start">
      <ObjectDetailsCard
        objectSchema={objectSchema}
        objectData={objectData}
        permission={permission}
        className="shrink-0 grow overflow-x-hidden p-0 md:col-span-2"
      />
      <Col>
        <ObjectProfilesGroupsCard
          objectSchema={objectSchema}
          objectData={objectData}
          permission={permission}
        />
        <ObjectActivitiesCard objectKind={objectData.__typename} objectId={objectData.id} />
      </Col>
    </div>
  );
}
