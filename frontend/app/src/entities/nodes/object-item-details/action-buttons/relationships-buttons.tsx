import { QSP } from "@/config/qsp";
import { ADD_RELATIONSHIP } from "@/entities/nodes/relationships/api/addRelationship";
import { Permission } from "@/entities/permission/types";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import { ModelSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { useMutation } from "@/shared/api/graphql/useQuery";
import { queryClient } from "@/shared/api/rest/client";
import { ButtonWithTooltip } from "@/shared/components/buttons/button-primitive";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import DynamicForm from "@/shared/components/form/dynamic-form";
import ObjectForm from "@/shared/components/form/object-form";
import { SelectOption } from "@/shared/components/inputs/select-old";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { useState } from "react";
import { useParams } from "react-router";
import { toast } from "react-toastify";
import { StringParam, useQueryParam } from "use-query-params";

interface RelationshipsButtonsProps {
  permission: Permission;
  schema: ModelSchema;
}

export function RelationshipsButtons({
  permission,
  schema: parentSchema,
}: RelationshipsButtonsProps) {
  const { objectKind, objectid } = useParams();
  const [addRelationship] = useMutation(ADD_RELATIONSHIP);
  const generics = useAtomValue(genericSchemasAtom);
  const schemaList = useAtomValue(nodeSchemasAtom);
  const [relationshipTab] = useQueryParam(QSP.TAB, StringParam);

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
  console.log("peerRelationshipSchema: ", peerRelationshipSchema);

  const [showAddDrawer, setShowAddDrawer] = useState(false);

  let options: SelectOption[] = [];

  if (generic) {
    (generic.used_by || []).forEach((kind) => {
      const relatedSchema = schemaList.find((s) => s.kind === kind);

      if (relatedSchema) {
        options.push({
          id: relatedSchema.kind,
          name: relatedSchema.name,
        });
      }
    });
  } else {
    const relatedSchema = schemaList.find((s) => s.kind === relationshipSchema?.peer);

    if (relatedSchema) {
      options.push({
        id: relatedSchema.kind,
        name: relatedSchema.label ?? relatedSchema.name,
      });
    }
  }

  const handleSubmit = async (data: any) => {
    const { relation } = data;

    if (relation?.id || relation?.from_pool) {
      await addRelationship({
        variables: {
          objectId: objectid,
          relationshipIds: [{ id: relation.id }],
          relationshipName: relationshipSchema?.name,
        },
      });

      await graphqlClient.refetchQueries({
        include: [objectKind!, `GetObjectRelationships_${objectKind}`],
      });
      queryClient.invalidateQueries({
        predicate: (query) => query.queryKey.includes("objects"),
      });

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
        {relationshipSchemaData?.kind === "Component" &&
        peerRelationshipSchema?.kind === "Parent" &&
        peerRelationshipSchema.optional === false ? (
          <ObjectForm
            onSuccess={async ({ relation }) => {
              await handleSubmit({ relation: relation.value });
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
                label: relationshipSchema?.label,
                type: "relationship",
                relationship: { ...relationshipSchema, cardinality: "one", inherited: true },
                schema: relationshipSchemaData,
                options,
              },
            ]}
            onSubmit={async ({ relation }) => {
              await handleSubmit({ relation: relation.value });
            }}
            onCancel={() => {
              setShowAddDrawer(false);
            }}
            className="w-full p-4"
          />
        )}
      </SlideOver>
    </>
  );
}
