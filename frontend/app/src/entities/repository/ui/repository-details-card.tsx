import { Card, CardHeader } from "@infrahub/ui";
import { useId } from "react";

import type { NodeObjectWithMetadata } from "@/entities/nodes/object/domain/model/node";
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

  if (!objectSchema.attributes?.length && !objectSchema.relationships?.length) return null;

  return (
    <Card
      role="region"
      aria-labelledby={caption ? `${titleId} ${captionId}` : titleId}
      data-testid={testId}
    >
      <CardHeader>
        <h2 id={titleId}>{title}</h2>
        {caption && (
          <p id={captionId} className="font-normal text-foreground-muted text-xs">
            {caption}
          </p>
        )}
      </CardHeader>

      <ObjectDataDisplay
        objectSchema={objectSchema}
        objectData={objectData}
        permission={permission}
      />
    </Card>
  );
}
