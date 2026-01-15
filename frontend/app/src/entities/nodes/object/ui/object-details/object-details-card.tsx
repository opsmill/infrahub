import ObjectEditSlideOverTrigger from "@/shared/components/form/object-edit-slide-over-trigger";
import { Card, CardWithBorder } from "@/shared/components/ui/card";

import { ObjectDataDisplay } from "@/entities/nodes/object/ui/object-details/object-data-display/object-data-display";
import type { NodeObjectWithMetadata } from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";

interface ObjectDetailsCardProps {
  objectSchema: ModelSchema;
  objectData: NodeObjectWithMetadata;
  permission: Permission;
  className?: string;
}

export function ObjectDetailsCard({
  objectSchema,
  objectData,
  permission,
  className,
}: ObjectDetailsCardProps) {
  return (
    <Card className={className} data-testid="object-details">
      <CardWithBorder.Title className="flex items-center border-gray-200 border-b">
        Details
        <ObjectEditSlideOverTrigger
          data={objectData}
          schema={objectSchema}
          permission={permission}
          variant="ghost"
          className="ml-auto size-5 text-neutral-400 hover:bg-neutral-200 hover:text-neutral-500"
        />
      </CardWithBorder.Title>

      <ObjectDataDisplay
        objectSchema={objectSchema}
        objectData={objectData}
        permission={permission}
      />
    </Card>
  );
}
