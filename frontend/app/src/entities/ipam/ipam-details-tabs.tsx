import { IdCardIcon } from "lucide-react";

import { Row } from "@/shared/components/container";
import { LinkTab } from "@/shared/components/ui/link";

import { constructPathForIpam } from "@/entities/ipam/utils";
import { ObjectDetailsTab } from "@/entities/nodes/object/ui/object-details/object-details-tab";
import { getRelationshipsVisibleInTab } from "@/entities/nodes/object/utils/get-relationships-visible-in-tab";
import type { NodeObject } from "@/entities/nodes/types";
import type { ModelSchema } from "@/entities/schema/types";

export interface IpamDetailsTabsProps {
  objectSchema: ModelSchema;
  objectData: NodeObject;
}

export function IpamDetailsTabs({ objectSchema, objectData }: IpamDetailsTabsProps) {
  const relationshipVisible = getRelationshipsVisibleInTab(objectSchema.relationships ?? []);

  return (
    <Row className="border-gray-200 border-b">
      <LinkTab href={constructPathForIpam("details")}>
        <IdCardIcon className="size-4" />
        Details
      </LinkTab>

      {relationshipVisible.map((relationship) => {
        return (
          <ObjectDetailsTab
            key={relationship.name}
            parentKind={objectSchema.kind as string}
            parentId={objectData.id}
            relationship={relationship}
          />
        );
      })}
    </Row>
  );
}
