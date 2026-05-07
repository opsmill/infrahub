import { useParams } from "react-router";

import { useObjectDetailsOutlet } from "@/entities/nodes/object/ui/object-details/use-object-details-outlet";
import { ObjectRelationshipsManager } from "@/entities/nodes/relationships/ui/object-relationships-manager";

export function Component() {
  const { objectSchema, objectData, permission } = useObjectDetailsOutlet();
  const { relationshipName } = useParams() as { relationshipName: string };

  return (
    <ObjectRelationshipsManager
      parentNodeSchema={objectSchema}
      parentNodeData={objectData}
      relationshipName={relationshipName}
      permission={permission}
    />
  );
}
