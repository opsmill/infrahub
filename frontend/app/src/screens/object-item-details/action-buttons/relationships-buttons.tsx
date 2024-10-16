import { ButtonWithTooltip } from "@/components/buttons/button-primitive";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import DynamicForm from "@/components/form/dynamic-form";
import { SelectOption } from "@/components/inputs/select";
import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { QSP } from "@/config/qsp";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { ADD_RELATIONSHIP } from "@/graphql/mutations/relationships/addRelationship";
import { useMutation } from "@/hooks/useQuery";
import { Permission } from "@/screens/permission/types";
import { genericsState, schemaState } from "@/state/atoms/schema.atom";
import { Permission } from "@/utils/permissions";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { StringParam, useQueryParam } from "use-query-params";

interface RelationshipsButtonsProps {
  permission: Permission;
}

export function RelationshipsButtons({ permission }: RelationshipsButtonsProps) {
  const { objectKind, objectid } = useParams();
  const [addRelationship] = useMutation(ADD_RELATIONSHIP);
  const generics = useAtomValue(genericsState);
  const schemaList = useAtomValue(schemaState);
  const [relationshipTab] = useQueryParam(QSP.TAB, StringParam);

  const parentSchema = schemaList.find((s) => s.kind === objectKind);
  const parentGeneric = generics.find((s) => s.kind === objectKind);
  const relationshipSchema = parentSchema?.relationships?.find((r) => r?.name === relationshipTab);
  const relationshipGeneric = parentGeneric?.relationships?.find(
    (r) => r?.name === relationshipTab
  );
  const relationshipSchemaData = relationshipSchema || relationshipGeneric;
  const generic = generics.find((g) => g.kind === relationshipSchemaData?.kind);

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
          relationshipIds: [relation],
          relationshipName: relationshipSchema?.name,
        },
      });

      await graphqlClient.refetchQueries({
        include: [objectKind!, `GetObjectRelationships_${objectKind}`],
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
      </SlideOver>
    </>
  );
}
