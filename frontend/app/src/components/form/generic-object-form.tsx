import NoDataFound from "@/screens/errors/no-data-found";
import { GenericSelector } from "@/components/form/generic-selector";
import { useState } from "react";
import { iGenericSchema } from "@/state/atoms/schema.atom";
import { ObjectFormProps } from "@/components/form/object-form";
import { NodeWithProfileForm } from "@/components/form/node-with-profile-form";

interface GenericObjectFormProps extends Omit<ObjectFormProps, "kind"> {
  schema: iGenericSchema;
}

export const GenericObjectForm = ({ schema, ...props }: GenericObjectFormProps) => {
  const [kindToCreate, setKindToCreate] = useState<string | undefined>(
    schema.used_by?.length === 1 ? schema.used_by[0] : undefined
  );

  if (!schema.used_by || schema.used_by?.length === 0) {
    return (
      <NoDataFound message="This generic schema is not currently associated with any nodes. To create an instance, you need to first link this generic to at least one node type. Please check your schema configuration." />
    );
  }

  return (
    <>
      <GenericSelector
        kindInheritingFromGeneric={schema.used_by}
        value={kindToCreate}
        onChange={setKindToCreate}
      />
      {kindToCreate && <NodeWithProfileForm kind={kindToCreate} {...props} />}
    </>
  );
};
