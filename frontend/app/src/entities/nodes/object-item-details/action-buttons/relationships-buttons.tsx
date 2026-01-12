import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { useQueryState } from "nuqs";
import { useState } from "react";
import { toast } from "react-toastify";

import { queryClient } from "@/shared/api/rest/client";
import { ButtonWithTooltip } from "@/shared/components/buttons/button-primitive";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import DynamicForm from "@/shared/components/form/dynamic-form";
import ObjectForm from "@/shared/components/form/object-form";
import { FormContext } from "@/shared/components/form/utils/form-context";
import type { SelectOption } from "@/shared/components/inputs/select-old";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { QSP } from "@/shared/config/qsp";

import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import { useAddRelationships } from "@/entities/nodes/relationships/domain/add-relationships/add-relationships.mutation";
import type { NodeObject } from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import type { ModelSchema, RelationshipSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface RelationshipsButtonsProps {
  permission: Permission;
  schema: ModelSchema;
  objectDetailsData: NodeObject;
}

export function RelationshipsButtons({
  permission,
  schema: parentSchema,
  objectDetailsData,
}: RelationshipsButtonsProps) {
  const objectKind = objectDetailsData.__typename;
  const objectId = objectDetailsData.id;
  const { mutateAsync: addRelationship } = useAddRelationships();
  const generics = useAtomValue(genericSchemasAtom);
  const schemaList = useAtomValue(nodeSchemasAtom);
  const [relationshipTab] = useQueryState(QSP.TAB);

  const parentGeneric = generics.find((s) => s.kind === objectKind);
  const relationshipSchema = parentSchema?.relationships?.find((r) => r?.name === relationshipTab);
  const relationshipGeneric = parentGeneric?.relationships?.find((r) => {
    return r?.name === relationshipTab;
  });
  const relationshipSchemaData = relationshipSchema || relationshipGeneric;
  const generic = generics.find((g) => g.kind === relationshipSchemaData?.kind);
  const peerSchema = useSchema(relationshipSchemaData?.peer);
  const peerRelationshipSchema = peerSchema.schema?.relationships?.find((r) => {
    return r.peer === objectKind;
  });

  const [showAddDrawer, setShowAddDrawer] = useState(false);

  let options: SelectOption[] = [];

  if (generic) {
    (generic.used_by || []).forEach((kind) => {
      const relatedSchema = schemaList.find((s) => s.kind === kind);

      if (relatedSchema) {
        options.push({
          id: relatedSchema.kind!,
          name: relatedSchema.name,
        });
      }
    });
  } else {
    const relatedSchema = schemaList.find((s) => s.kind === relationshipSchema?.peer);

    if (relatedSchema) {
      options.push({
        id: relatedSchema.kind!,
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
      await addRelationship({
        objectId,
        relationshipIds: [relation.id],
        relationshipName: relationshipSchema!.name,
      });

      await handleRefetch();

      toast(
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={`Association with ${relationshipSchema?.peer} added`}
        />
      );

      setShowAddDrawer(false);
    }
  };

  return (
    <>
      <ButtonWithTooltip
        disabled={!permission.create.isAllowed}
        tooltipEnabled
        tooltipContent={permission.create.message ?? "Add relationship"}
        onClick={() => setShowAddDrawer(true)}
        data-testid="open-relationship-form-button"
        size="sm"
      >
        <Icon icon="mdi:plus" className="mr-1.5" aria-hidden="true" /> Add{" "}
        {relationshipSchema?.label ?? relationshipSchema?.kind ?? "relationship"}
      </ButtonWithTooltip>

      <SlideOver
        title={
          parentSchema && (
            <SlideOverTitle
              schema={parentSchema}
              currentObjectLabel={relationshipSchema?.label}
              title={`Associate a new ${relationshipSchema?.label}`}
              subtitle={`Add a new ${relationshipSchema?.label} to the current object`}
            />
          )
        }
        open={showAddDrawer}
        setOpen={setShowAddDrawer}
      >
        <FormContext value={{ parentSchema, parentData: objectDetailsData }}>
          {parentSchema &&
          relationshipSchemaData?.kind === "Component" &&
          peerRelationshipSchema?.kind === "Parent" &&
          peerRelationshipSchema.optional === false ? (
            <ObjectForm
              onSuccess={async () => {
                await handleRefetch();
                setShowAddDrawer(false);
              }}
              onCancel={() => {
                setShowAddDrawer(false);
              }}
              kind={relationshipSchemaData?.peer!}
            />
          ) : (
            <DynamicForm
              fields={[
                {
                  name: "relation",
                  label: relationshipSchema?.label!,
                  type: "relationship",
                  relationship: {
                    ...relationshipSchema,
                    cardinality: "one",
                    inherited: true,
                  } as RelationshipSchema,
                  options,
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
