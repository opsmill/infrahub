import { EyeIcon, EyeOffIcon } from "lucide-react";
import React from "react";

import { Button } from "@/shared/components/ui/button";
import { Card, CardWithBorder } from "@/shared/components/ui/card";
import { classNames } from "@/shared/utils/common";

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
}

export function ObjectDetailsCard({
  objectSchema,
  objectData,
  permission,
  className,
}: ObjectDetailsCardProps) {
  const [showExtra, setShowExtra] = React.useState(false);
  const schemaHasExtraFields = hasExtraFields(objectSchema);

  return (
    <Card className={classNames("overflow-x-hidden p-0", className)} data-testid="object-details">
      <CardWithBorder.Title className="flex justify-between border-gray-200 border-b">
        Details
        {schemaHasExtraFields && (
          <Button
            variant="ghost"
            size="sm"
            className="h-auto gap-1 pr-0 text-xs"
            onClick={() => setShowExtra((prev) => !prev)}
          >
            {showExtra ? <EyeOffIcon className="size-3.5" /> : <EyeIcon className="size-3.5" />}
            Extra
          </Button>
        )}
      </CardWithBorder.Title>

      <ObjectDataDisplay
        objectSchema={objectSchema}
        objectData={objectData}
        permission={permission}
        showExtra={showExtra}
      />
    </Card>
  );
}
