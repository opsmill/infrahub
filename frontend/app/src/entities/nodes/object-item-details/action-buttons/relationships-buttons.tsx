import { Icon } from "@iconify-icon/react";
import { Button } from "@infrahub/ui";
import { useAtomValue } from "jotai";
import { useState } from "react";
import { toast } from "react-toastify";

import { queryClient } from "@/shared/api/rest/client";
import { Tooltip } from "@/shared/components/aria/tooltip";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import DynamicForm from "@/shared/components/form/dynamic-form";
import ObjectForm from "@/shared/components/form/object-form";
import { FormContext } from "@/shared/components/form/utils/form-context";
import type { SelectOption } from "@/shared/components/inputs/select-old";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import { useAddRelationships } from "@/entities/nodes/relationships/ui/queries/add-relationships.mutation";
import type { NodeObject } from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import { getPoolKindFromSchema } from "@/entities/resource-manager/utils/get-pool-kind-from-schema";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import type { ModelSchema, RelationshipSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface RelationshipsButtonsProps {
  permission: Permission;
  schema: ModelSchema;
  objectDetailsData: NodeObject;
  relationshipName: string;
}

export function RelationshipsButtons({
  permission,
  schema: parentSchema,
  objectDetailsData,
  relationshipName,
}: RelationshipsButtonsProps) {
  const objectKind = objectDetailsData.__typename;
  const objectId = objectDetailsData.id;
  const { mutateAsync: addRelationship } = useAddRelationships();
  const generics = useAtomValue(genericSchemasAtom);
  const schemaList = useAtomValue(nodeSchemasAtom);

  const parentGeneric = generics.find((s) => s.kind === objectKind);
  const relationshipSchema = parentSchema.relationships?.find((r) => r?.name === relationshipName);
  const relationshipGeneric = parentGeneric?.relationships?.find(
    (r) => r?.name === relationshipName
  );
  const relationshipSchemaData = relationshipSchema ?? relationshipGeneric;
  const generic = generics.find((g) => g.kind === relationshipSchemaData?.kind);
  const peerSchema = useSchema(relationshipSchemaData?.peer);
  const peerRelationshipSchema = peerSchema.schema?.relationships?.find(
    (r) => r.peer === objectKind
  );

  const poolKind = peerSchema.schema ? getPoolKindFromSchema(peerSchema.schema) : null;

  const [showAddDrawer, setShowAddDrawer] = useState(false);

  if (!relationshipSchemaData) {
    // The route guarantees relationshipName, but the schema lookup can fail
    // (e.g. stale URL after a schema change). Render nothing rather than crash.
    return null;
  }

  const options: SelectOption[] = [];

  if (generic) {
    for (const kind of generic.used_by ?? []) {
      const relatedSchema = schemaList.find((s) => s.kind === kind);
      if (relatedSchema?.kind) {
        options.push({ id: relatedSchema.kind, name: relatedSchema.name });
      }
    }
  } else {
    const relatedSchema = schemaList.find((s) => s.kind === relationshipSchemaData.peer);
    if (relatedSchema?.kind) {
      options.push({
        id: relatedSchema.kind,
        name: relatedSchema.label ?? relatedSchema.name,
      });
    }
  }

  const handleRefetch = async () => {
    await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
  };

  const handleSubmit = async (data: any) => {
    const { relation } = data;

    if (relation?.id || relation?.from_pool) {
      const relationshipId = relation.from_pool
        ? { from_pool: { id: relation.from_pool.id } }
        : relation.id;

      await addRelationship({
        objectId,
        relationshipIds: [relationshipId],
        relationshipName,
      });

      await handleRefetch();

      toast(
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={`Association with ${relationshipSchemaData.peer} added`}
        />
      );

      setShowAddDrawer(false);
    }
  };

  const { isAllowed: isAddAllowed, message: addTooltipMessage } = permission.create;
  const relationshipLabel =
    relationshipSchemaData.label ?? relationshipSchemaData.kind ?? "relationship";

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

      <SlideOver
        title={
          <SlideOverTitle
            schema={parentSchema}
            currentObjectLabel={relationshipSchemaData.label}
            title={`Associate a new ${relationshipLabel}`}
            subtitle={`Add a new ${relationshipLabel} to the current object`}
          />
        }
        open={showAddDrawer}
        setOpen={setShowAddDrawer}
      >
        <FormContext value={{ parentSchema, parentData: objectDetailsData }}>
          {relationshipSchemaData.kind === "Component" &&
          peerRelationshipSchema?.kind === "Parent" &&
          peerRelationshipSchema.optional === false &&
          relationshipSchemaData.peer ? (
            <ObjectForm
              onSuccess={async () => {
                await handleRefetch();
                setShowAddDrawer(false);
              }}
              onCancel={() => {
                setShowAddDrawer(false);
              }}
              kind={relationshipSchemaData.peer}
            />
          ) : (
            <DynamicForm
              fields={[
                {
                  name: "relation",
                  label: relationshipLabel,
                  type: "relationship",
                  relationship: {
                    ...relationshipSchemaData,
                    cardinality: "one",
                    inherited: true,
                  } as RelationshipSchema,
                  options,
                  pool:
                    poolKind && peerSchema.schema?.kind
                      ? {
                          kind: poolKind,
                          defaultAllocatedObjectKind: peerSchema.schema.kind,
                        }
                      : undefined,
                },
              ]}
              onSubmit={async ({ relation }) => {
                await handleSubmit({ relation: relation?.value });
              }}
              onCancel={() => {
                setShowAddDrawer(false);
              }}
              className="w-full p-4"
            />
          )}
        </FormContext>
      </SlideOver>
    </>
  );
}
