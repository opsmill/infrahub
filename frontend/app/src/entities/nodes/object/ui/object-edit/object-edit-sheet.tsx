import { Sheet } from "@infrahub/ui";

import { queryClient } from "@/shared/api/rest/client";
import { SlideOverTitle } from "@/shared/components/display/slide-over";

import ObjectEdit from "@/entities/nodes/object/ui/object-edit/object-item-edit-paginated";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

interface ObjectEditSheetProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  schema: ModelSchema;
  objectId: string;
  objectLabel: string;
  objectKind?: string;
  subtitle?: string | null;
  extraRelationshipNames?: string[];
}

export function ObjectEditSheet({
  isOpen,
  onOpenChange,
  schema,
  objectId,
  objectLabel,
  objectKind = schema.kind,
  subtitle,
  extraRelationshipNames,
}: ObjectEditSheetProps) {
  return (
    <Sheet isOpen={isOpen} onOpenChange={onOpenChange}>
      <SlideOverTitle
        schema={schema}
        currentObjectLabel={objectLabel}
        title={`Edit ${objectLabel}`}
        subtitle={subtitle}
      />
      <ObjectEdit
        closeDrawer={() => onOpenChange(false)}
        onUpdateComplete={async () => {
          await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
          onOpenChange(false);
        }}
        objectId={objectId}
        objectKind={objectKind}
        extraRelationshipNames={extraRelationshipNames}
      />
    </Sheet>
  );
}
