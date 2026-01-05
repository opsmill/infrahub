import { useAtomValue } from "jotai";
import { useEffect } from "react";
import { useFormContext } from "react-hook-form";

import { namespacesAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { DEFAULT_FORM_FIELD_VALUE } from "./constants";
import DropdownField from "./fields/dropdown.field";
import type { FormAttributeValue } from "./type";
import { isRequired } from "./utils/validation";

export const NameSelect = () => {
  const namespaces = useAtomValue(namespacesAtom);
  const nodes = useAtomValue(nodeSchemasAtom);

  const form = useFormContext();
  const selectedNamespaceField: FormAttributeValue = form.watch("namespace");
  const selectedNameField: FormAttributeValue = form.watch("name");

  const namespaceOptions = [
    {
      value: "*",
      label: "*",
    },
    ...namespaces.map((namespace) => {
      return {
        value: namespace.name,
        label: namespace.name,
      };
    }),
  ];

  const selectedNamespace =
    selectedNamespaceField?.value === "*"
      ? { value: "*", name: "*" }
      : namespaces.find((namespace) => {
          return namespace.name === selectedNamespaceField?.value;
        });

  const nameOptions = [
    {
      value: "*",
      label: "*",
    },
    ...nodes
      .filter((node) => {
        if (!selectedNamespace || selectedNamespace?.name === "*") return true;

        return node.namespace === selectedNamespace?.name;
      })
      .map((node) => ({
        value: node.name,
        label: node.label,
        badge: node.namespace,
      })),
  ];

  useEffect(() => {
    // Break if namespace already set
    if (selectedNamespaceField?.value) return;

    // Break if no name is provided
    if (!selectedNameField?.value) return;

    // Get current node from form field value
    const currentNode = nodes.find((node) => node.name === selectedNameField?.value);

    if (!currentNode) return;

    form.setValue("namespace", { value: currentNode.namespace, label: currentNode.namespace });
  }, [selectedNameField?.value]);

  return (
    <>
      <DropdownField
        name={"namespace"}
        label="Namespace"
        defaultValue={DEFAULT_FORM_FIELD_VALUE}
        items={namespaceOptions}
        rules={{ validate: { required: isRequired } }}
      />

      <DropdownField
        key={selectedNamespaceField?.value}
        name={"name"}
        label="Name"
        defaultValue={DEFAULT_FORM_FIELD_VALUE}
        items={nameOptions}
        rules={{ validate: { required: isRequired } }}
      />
    </>
  );
};
