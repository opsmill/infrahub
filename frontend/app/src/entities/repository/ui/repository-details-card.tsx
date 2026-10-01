import { Button, Card, CardHeader } from "@infrahub/ui";
import { EyeIcon, EyeOffIcon } from "lucide-react";
import { useId, useState } from "react";

import type { NodeObjectWithMetadata } from "@/entities/nodes/object/domain/model/node";
import { hasExtraFields } from "@/entities/nodes/object/domain/rules/has-extra-fields";
import { ObjectDataDisplay } from "@/entities/nodes/object/ui/object-details/object-data-display/object-data-display";
import type { Permission } from "@/entities/permission/domain/model/permission";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

interface RepositoryDetailsCardProps {
  title: string;
  caption?: string;
  testId: string;
  objectSchema: ModelSchema;
  objectData: NodeObjectWithMetadata;
  permission: Permission;
}

export function RepositoryDetailsCard({
  title,
  caption,
  testId,
  objectSchema,
  objectData,
  permission,
}: RepositoryDetailsCardProps) {
  const id = useId();
  const titleId = `${id}-title`;
  const captionId = `${id}-caption`;
  const [showExtra, setShowExtra] = useState(false);
  const schemaHasExtraFields = hasExtraFields(objectSchema);

  if (!objectSchema.attributes?.length && !objectSchema.relationships?.length) return null;

  return (
    <Card
      role="region"
      aria-labelledby={caption ? `${titleId} ${captionId}` : titleId}
      data-testid={testId}
    >
      <CardHeader className="flex justify-between">
        <div>
          <h2 id={titleId}>{title}</h2>
          {caption && (
            <p id={captionId} className="font-normal text-foreground-muted text-xs">
              {caption}
            </p>
          )}
        </div>

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
      />
    </Card>
  );
}
