import { Button, Card, CardHeader } from "@infrahub/ui";
import { EyeIcon, EyeOffIcon } from "lucide-react";
import React from "react";

import { ObjectDataDisplay } from "@/entities/nodes/object/ui/object-details/object-data-display/object-data-display";
import { hasExtraFields } from "@/entities/nodes/object/utils/has-extra-fields";
import type { NodeObjectWithMetadata } from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";

interface ObjectDetailsCardProps {
  objectSchema: ModelSchema;
  objectData: NodeObjectWithMetadata;
  permission: Permission;
  className?: string;
  excludeRelationships?: string[];
}

export function ObjectDetailsCard({
  objectSchema,
  objectData,
  permission,
  className,
  excludeRelationships,
}: ObjectDetailsCardProps) {
  const [showExtra, setShowExtra] = React.useState(false);
  const schemaHasExtraFields = hasExtraFields(objectSchema);

  return (
    <Card className={className} data-testid="object-details">
      <CardHeader className="flex justify-between">
        Details
        {schemaHasExtraFields && (
          <Button
            variant="ghost"
            size="sm"
            className="h-auto gap-1 pr-0 text-xs"
            onPress={() => setShowExtra((prev) => !prev)}
          >
            {showExtra ? <EyeOffIcon className="size-3.5" /> : <EyeIcon className="size-3.5" />}
            Extra
          </Button>
        )}
      </CardHeader>

      <ObjectDataDisplay
        objectSchema={objectSchema}
        objectData={objectData}
        permission={permission}
        showExtra={showExtra}
        excludeRelationships={excludeRelationships}
      />
    </Card>
  );
}
