import { Card, CardWithBorder } from "@/shared/components/ui/card";
import { classNames } from "@/shared/utils/common";

import { ObjectDataDisplay } from "@/entities/nodes/object/ui/object-details/object-data-display/object-data-display";
import type { NodeObjectWithMetadata } from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";

interface ObjectDetailsCardProps {
  objectSchema: ModelSchema;
  objectData: NodeObjectWithMetadata;
  permission: Permission;
  className?: string;
  /** Attribute names to exclude from display */
  excludeAttributes?: string[];
  /** Relationship names to exclude from display */
  excludeRelationships?: string[];
  /** Relationship kinds to exclude from display */
  excludeRelationshipKinds?: string[];
}

export function ObjectDetailsCard({
  objectSchema,
  objectData,
  permission,
  className,
  excludeAttributes,
  excludeRelationships,
  excludeRelationshipKinds,
}: ObjectDetailsCardProps) {
  return (
    <Card className={classNames("overflow-x-hidden p-0", className)} data-testid="object-details">
      <CardWithBorder.Title className="border-gray-200 border-b">Details</CardWithBorder.Title>

      <ObjectDataDisplay
        objectSchema={objectSchema}
        objectData={objectData}
        permission={permission}
        excludeAttributes={excludeAttributes}
        excludeRelationships={excludeRelationships}
        excludeRelationshipKinds={excludeRelationshipKinds}
      />
    </Card>
  );
}
