import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { createObject } from "@/entities/nodes/api/createObject";
import { updateObjectWithId } from "@/entities/nodes/api/updateObjectWithId";
import { AttributeType, RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { NODE_TRIGGER_RELATIONSHIP_MATCH, NODE_TRIGGER_RULE } from "@/entities/triggers/constants";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { Button } from "@/shared/components/buttons/button-primitive";
import { DynamicInput } from "@/shared/components/form/dynamic-form";
import { LabelFormField } from "@/shared/components/form/fields/common";
import DropdownField from "@/shared/components/form/fields/dropdown.field";
import PeerField from "@/shared/components/form/fields/peer.field";
import { NodeFormProps } from "@/shared/components/form/node-form";
import {
  DynamicDropdownFieldProps,
  DynamicFieldProps,
  FormAttributeValue,
  FormFieldValue,
} from "@/shared/components/form/type";
import { useCurrentFormContext, useFormContext } from "@/shared/components/form/utils/form-context";
import { getCurrentFieldValue } from "@/shared/components/form/utils/getFieldDefaultValue";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { getRelationshipDefaultValue } from "@/shared/components/form/utils/getRelationshipDefaultValue";
import { getCreateMutationFromFormDataOnly } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { DropdownOption } from "@/shared/components/inputs/dropdown";
import { Skeleton } from "@/shared/components/skeleton";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Form, FormSubmit } from "@/shared/components/ui/form";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { stringifyWithoutQuotes } from "@/shared/utils/string";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { useEffect, useState } from "react";
import { FieldValues, useForm } from "react-hook-form";
import { toast } from "react-toastify";

interface NodeRelationshipMatchFormProps extends NodeFormProps {}

export const NodeRelationshipMatchForm = ({
  currentObject,
  objectTemplate,
  isUpdate,
  onSuccess,
  onCancel,
  ...props
}: NodeRelationshipMatchFormProps) => {
  const { currentBranch } = useCurrentBranch();
  const date = useAtomValue(datetimeAtom);
  const { parentData, parentSchema } = useCurrentFormContext();

  const schemaFields = getFormFieldsFromSchema({
    ...props,
    initialObject: currentObject,
    isUpdate,
    parentData,
    parentSchema,
  });

  const fields = schemaFields.filter((field) => {
    return field.name !== "relationship_name" && field.name !== "peer";
  });

  const defaultPeerValue = getCurrentFieldValue("peer", {
    peer: currentObject?.peer as AttributeType,
  });

  const defaultValues = {
    relationship_name: getCurrentFieldValue("relationship_name", {
      relationship_name: currentObject?.relationship_name as AttributeType,
    }),
    added: getCurrentFieldValue("added", {
      added: currentObject?.added as AttributeType,
    }),
    peer: {
      source: defaultPeerValue?.source,
      value: { id: defaultPeerValue?.value },
    },
    value_match: getCurrentFieldValue("value_match", {
      value_match: currentObject?.value_match as AttributeType,
    }),
    member_of_group: getRelationshipDefaultValue({
      relationshipData: currentObject?.member_of_group as RelationshipType | undefined,
      relationshipName: "member_of_group",
      objectTemplate,
    }),
    trigger: getRelationshipDefaultValue({
      relationshipData: currentObject?.trigger as RelationshipType | undefined,
      relationshipName: "trigger",
      objectTemplate,
      schema: props.schema,
      parentData,
      parentSchema,
    }),
  };

  const form = useForm<FieldValues>({
    defaultValues,
  });

  async function handleSubmit(data: Record<string, FormFieldValue>) {
    try {
      const newObject = getCreateMutationFromFormDataOnly(data, currentObject);

      if (!Object.keys(newObject).length) {
        return;
      }

      const mutationString = currentObject?.id
        ? updateObjectWithId({
            kind: NODE_TRIGGER_RELATIONSHIP_MATCH,
            data: stringifyWithoutQuotes({
              id: currentObject.id,
              ...newObject,
              peer: newObject?.peer?.id && {
                value: newObject?.peer?.id,
              },
            }),
          })
        : createObject({
            kind: NODE_TRIGGER_RELATIONSHIP_MATCH,
            data: stringifyWithoutQuotes({
              ...newObject,
              peer: newObject?.peer?.id && {
                value: newObject?.peer?.id,
              },
            }),
          });

      const mutation = gql`
        ${mutationString}
      `;

      const result = await graphqlClient.mutate({
        mutation,
        context: {
          branch: currentBranch.name,
          date,
        },
      });

      if (currentObject?.id) {
        toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Node relationship match updated!"} />, {
          toastId: "alert-success-node-relationship-match-updated",
        });
      } else {
        toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Node relationship match created!"} />, {
          toastId: "alert-success-node-relationship-match-created",
        });
      }

      if (onSuccess)
        await onSuccess(
          result?.data?.[`${NODE_TRIGGER_RELATIONSHIP_MATCH}${currentObject ? "Update" : "Create"}`]
        );
    } catch (error: unknown) {
      console.error("An error occurred while creating the object: ", error);
    }
  }

  return (
    <div className={"bg-white flex flex-col flex-1 overflow-auto p-4"}>
      <Form form={form} onSubmit={handleSubmit}>
        <NodeRelationshipField schemaFields={schemaFields} />

        {fields.map((field) => {
          return <DynamicInput key={field.name} {...field} />;
        })}

        <div className="text-right">
          {onCancel && (
            <Button variant="outline" className="mr-2" onClick={onCancel}>
              Cancel
            </Button>
          )}

          <FormSubmit>Save</FormSubmit>
        </div>
      </Form>
    </div>
  );
};

interface NodeRelationshipFieldProps {
  schemaFields: Array<DynamicFieldProps>;
}

const NodeRelationshipField = ({ schemaFields }: NodeRelationshipFieldProps) => {
  const form = useFormContext();

  const { schema } = useSchema(NODE_TRIGGER_RULE);
  const selectedTriggerField: FormAttributeValue = form.watch("trigger");
  const selectedRelationshipField: FormAttributeValue = form.watch("relationship_name");

  const { data, isPending } = useGetObject({
    objectId: selectedTriggerField.value?.id,
    objectSchema: schema,
  });

  const [peerKind, setPeerKind] = useState<string | null>(null);

  const relationshipField = schemaFields.find((field) => {
    return field.name === "relationship_name";
  }) as DynamicDropdownFieldProps;

  const peerField = schemaFields.find((field) => {
    return field.name === "peer";
  });

  const { schema: peerSchema } = useSchema(data?.node_kind?.value);

  const relationshipOptions: Array<DropdownOption> =
    peerSchema?.relationships?.map((relationship) => {
      return {
        value: relationship.name,
        label: relationship.label ?? relationship.name,
      };
    }) ?? [];

  useEffect(() => {
    if (!selectedRelationshipField?.value) {
      return setPeerKind(null);
    }

    const relationshipSchema = peerSchema?.relationships?.find((relationship) => {
      return relationship.name === selectedRelationshipField?.value;
    });

    setPeerKind(relationshipSchema?.peer ?? null);
  }, [selectedRelationshipField?.value, data?.node_kind?.value]);

  if (isPending) {
    return (
      <div className="space-y-4">
        <div className="space-y-2">
          <LabelFormField
            label={relationshipField.label}
            required={!!relationshipField?.rules?.required}
            description={relationshipField?.description}
          />

          <Skeleton className="h-10 w-full" />
        </div>
        <div className="space-y-2">
          <LabelFormField
            label={peerField.label}
            required={!!peerField?.rules?.required}
            description={peerField?.description}
          />

          <Skeleton className="h-10 w-full" />
        </div>
      </div>
    );
  }

  return (
    <>
      <DropdownField
        {...relationshipField}
        key={data?.node_kind?.value}
        items={relationshipOptions}
      />

      <PeerField
        {...peerField}
        key={`${data?.node_kind?.value}_${selectedRelationshipField?.value}`}
        peer={peerKind}
        disabled={!peerKind}
      />
    </>
  );
};
