import { Button, Sheet, Tooltip } from "@infrahub/ui";
import { useAtomValue } from "jotai";
import { useState } from "react";

import { queryClient } from "@/shared/api/rest/client";
import { Icon } from "@/shared/components/display/icon";
import { SlideOverTitle } from "@/shared/components/display/slide-over";

import type { NodeObject } from "@/entities/nodes/object/domain/model/node";
import { AddRelationshipForm } from "@/entities/nodes/object/ui/object-details/action-buttons/add-relationship-form";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import type { Permission } from "@/entities/permission/domain/model/permission";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { genericSchemasAtom } from "@/entities/schema/stores/schema.atom";

interface RelationshipsButtonsProps {
  permission: Permission;
  schema: ModelSchema;
  objectDetailsData: NodeObject;
  relationshipName: string;
}

export function RelationshipsButtons({
  permission,
  schema: objectSchema,
  objectDetailsData,
  relationshipName,
}: RelationshipsButtonsProps) {
  const objectKind = objectDetailsData.__typename;
  const generics = useAtomValue(genericSchemasAtom);

  const objectGeneric = generics.find((s) => s.kind === objectKind);
  const relationshipSchema =
    objectSchema.relationships?.find((r) => r?.name === relationshipName) ??
    objectGeneric?.relationships?.find((r) => r?.name === relationshipName);

  const [showAddDrawer, setShowAddDrawer] = useState(false);

  if (!relationshipSchema) {
    // A stale URL after a schema change can name a relationship the schema no longer has.
    return null;
  }

  const closeAfterSuccess = async () => {
    await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
    setShowAddDrawer(false);
  };

  const closeDrawer = () => {
    setShowAddDrawer(false);
  };

  const { isAllowed: isAddAllowed, message: addTooltipMessage } = permission.create;
  const relationshipLabel = relationshipSchema.label ?? relationshipSchema.kind ?? "relationship";

  return (
    <>
      <Tooltip message={addTooltipMessage ?? "Add relationship"}>
        <Button
          isDisabledAndFocusable={!isAddAllowed}
          onPress={() => setShowAddDrawer(true)}
          data-testid="open-relationship-form-button"
          size="sm"
        >
          <Icon icon="mdi:plus" aria-hidden="true" /> Add {relationshipLabel}
        </Button>
      </Tooltip>

      <Sheet isOpen={showAddDrawer} onOpenChange={setShowAddDrawer}>
        <SlideOverTitle
          schema={objectSchema}
          currentObjectLabel={relationshipSchema.label}
          title={`Associate a new ${relationshipLabel}`}
          subtitle={`Add a new ${relationshipLabel} to the current object`}
        />
        <AddRelationshipForm
          objectData={objectDetailsData}
          objectSchema={objectSchema}
          relationshipSchema={relationshipSchema}
          onSuccess={closeAfterSuccess}
          onCancel={closeDrawer}
        />
      </Sheet>
    </>
  );
}
