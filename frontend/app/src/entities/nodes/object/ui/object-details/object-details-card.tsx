import { Button, Card, CardHeader } from "@infrahub/ui";
import { EyeIcon, EyeOffIcon } from "lucide-react";
import React from "react";

import type { NodeObjectWithMetadata } from "@/entities/nodes/object/domain/model/node";
import { hasExtraFields } from "@/entities/nodes/object/domain/rules/has-extra-fields";
import { ObjectDataDisplay } from "@/entities/nodes/object/ui/object-details/object-data-display/object-data-display";
import type { Permission } from "@/entities/permission/domain/model/permission";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

interface ObjectDetailsCardProps {
  objectSchema: ModelSchema;
  objectData: NodeObjectWithMetadata;
  permission: Permission;
  className?: string;
  excludeRelationships?: string[];
  title?: React.ReactNode;
}

export function ObjectDetailsCard({
  objectSchema,
  objectData,
  permission,
  className,
  excludeRelationships,
  title = "Details",
}: ObjectDetailsCardProps) {
  const id = React.useId();
  const titleId = `${id}-title`;
  const [showExtra, setShowExtra] = React.useState(false);
  const schemaHasExtraFields = hasExtraFields(objectSchema);

  return (
    <Card
      className={className}
      role="region"
      aria-labelledby={titleId}
      data-testid="object-details"
    >
      <CardHeader className="flex items-center justify-between gap-2">
        <h2 id={titleId} className="flex min-w-0 items-center gap-2 whitespace-nowrap">
          {title}
        </h2>

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
