import DynamicForm from "@/components/form/dynamic-form";
import { DropdownFieldProps } from "@/components/form/fields/dropdown.field";
import { DynamicFieldProps, FormFieldValue } from "@/components/form/type";
import { getCreateMutationFromFormData } from "@/components/form/utils/mutations/getCreateMutationFromFormData";
import { Alert, ALERT_TYPES } from "@/components/ui/alert";
import { NUMBER_POOL_OBJECT, SCHEMA_ATTRIBUTE_KIND } from "@/config/constants";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { createObject } from "@/graphql/mutations/objects/createObject";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { schemaState } from "@/state/atoms/schema.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { classNames } from "@/utils/common";
import { stringifyWithoutQuotes } from "@/utils/string";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { useState } from "react";
import { toast } from "react-toastify";

export const NumberPoolForm = () => {
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const schemaList = useAtomValue(schemaState);
  const [node, setNode] = useState<string>("");

  const availableSchemaList = schemaList
    // ?.filter((schema) => schema.namespace !== "Core")
    ?.filter((schema) => !!schema.attributes?.find((attribute) => attribute.kind === "Number"));

  const selectedNode = availableSchemaList.find((schema) => schema.kind === node);
  console.log("selectedNode: ", selectedNode);

  const nodesOptions: DropdownFieldProps["items"] = availableSchemaList.map((schema) => ({
    id: schema.kind,
    name: schema.label,
  }));

  const attributesOptions: DropdownFieldProps["items"] = selectedNode?.attributes
    ?.filter((attribute) => attribute.kind === "Number")
    ?.map((attribute) => ({ id: attribute.name, name: attribute.label }));

  const fields: Array<DynamicFieldProps> = [
    {
      name: "name",
      label: "Name",
      type: SCHEMA_ATTRIBUTE_KIND.TEXT,
      rules: {
        required: true,
      },
    },
    {
      name: "descrption",
      label: "Description",
      type: SCHEMA_ATTRIBUTE_KIND.TEXT,
    },
    {
      name: "node",
      label: "Node",
      description: "The model of the object that requires integers to be allocated",
      type: SCHEMA_ATTRIBUTE_KIND.DROPDOWN,
      items: nodesOptions,
      onChange: (newNode: string) => setNode(newNode),
    },
    {
      name: "node_atttribute",
      label: "Node attribute",
      description: "The model of the object that requires integers to be allocated",
      type: SCHEMA_ATTRIBUTE_KIND.DROPDOWN,
      items: attributesOptions,
    },
    {
      name: "start_range",
      label: "Start range",
      description: "The start range for the pool",
      type: SCHEMA_ATTRIBUTE_KIND.NUMBER,
      rules: {
        required: true,
      },
    },
    {
      name: "end_range",
      label: "End range",
      description: "The end range for the pool",
      type: SCHEMA_ATTRIBUTE_KIND.NUMBER,
      rules: {
        required: true,
      },
    },
  ];

  async function handleSubmit(data: Record<string, FormFieldValue>) {
    try {
      const newObject = getCreateMutationFromFormData(fields, data);

      if (!Object.keys(newObject).length) {
        return;
      }

      const mutationString = createObject({
        kind: NUMBER_POOL_OBJECT,
        data: stringifyWithoutQuotes({
          ...newObject,
        }),
      });

      const mutation = gql`
        ${mutationString}
      `;

      await graphqlClient.mutate({
        mutation,
        context: {
          branch: branch?.name,
          date,
        },
      });

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Number pool created"} />, {
        toastId: "alert-success-number-pool-created",
      });
    } catch (error: unknown) {
      console.error("An error occurred while creating the object: ", error);
    }
  }

  return (
    <DynamicForm
      fields={fields}
      className={classNames("bg-custom-white flex flex-col flex-1 overflow-auto p-4")}
      onSubmit={handleSubmit}
    />
  );
};
