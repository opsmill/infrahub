import NoDataFound from "@/screens/errors/no-data-found";
import { tComboboxItem } from "@/components/ui/combobox";
import { GenericSelector } from "@/components/form/generic-selector";
import { useEffect, useState } from "react";
import { iGenericSchema, profilesAtom, schemaState } from "@/state/atoms/schema.atom";
import { useAtomValue } from "jotai/index";
import { NodeWithProfileForm, ObjectFormProps } from "@/components/form/object-form";

interface GenericObjectFormProps extends Omit<ObjectFormProps, "kind"> {
  schema: iGenericSchema;
}

export const GenericObjectForm = ({ schema, ...props }: GenericObjectFormProps) => {
  const nodeSchemas = useAtomValue(schemaState);
  const profileSchemas = useAtomValue(profilesAtom);
  const [kindToCreate, setKindToCreate] = useState<string>();

  useEffect(() => {
    if (schema.used_by?.length === 1) {
      setKindToCreate(schema.used_by[0]);
    }
  }, [schema?.kind]);

  if (!schema.used_by || schema.used_by?.length === 0) {
    return (
      <NoDataFound message="This generic schema is not currently associated with any nodes. To create an instance, you need to first link this generic to at least one node type. Please check your schema configuration." />
    );
  }

  const items: Array<tComboboxItem> = schema.used_by
    .map((kind) => {
      const relatedSchema = [...nodeSchemas, ...profileSchemas].find(
        (schema) => schema.kind === kind
      );

      if (!relatedSchema) return null;

      return {
        value: relatedSchema.kind,
        label: relatedSchema.label ?? relatedSchema.name,
        badge: relatedSchema.namespace,
      };
    })
    .filter((item) => !!item);

  return (
    <>
      <GenericSelector items={items} value={kindToCreate} onChange={setKindToCreate} />
      {kindToCreate && <NodeWithProfileForm kind={kindToCreate} {...props} />}
    </>
  );
};
