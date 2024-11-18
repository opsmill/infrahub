import { GenericSelector } from "@/components/form/generic-selector";
import ObjectForm, { ObjectFormProps } from "@/components/form/object-form";
import NoDataFound from "@/screens/errors/no-data-found";
import { iGenericSchema } from "@/state/atoms/schema.atom";
import { useState } from "react";

interface GenericObjectFormProps extends Omit<ObjectFormProps, "kind"> {
  genericSchema: iGenericSchema;
}

export const GenericObjectForm = ({ genericSchema, ...props }: GenericObjectFormProps) => {
  const [kindToCreate, setKindToCreate] = useState<string | null>(
    genericSchema.used_by?.length === 1 ? genericSchema.used_by[0] : null
  );

  if (!genericSchema.used_by || genericSchema.used_by?.length === 0) {
    return (
      <NoDataFound message="This generic schema is not currently associated with any nodes. To create an instance, you need to first link this generic to at least one node type. Please check your schema configuration." />
    );
  }

  return (
    <>
      <GenericSelector
        currentKind={genericSchema.kind as string}
        kindInheritingFromGeneric={genericSchema.used_by}
        value={kindToCreate}
        onChange={setKindToCreate}
      />

      {kindToCreate && <ObjectForm kind={kindToCreate} {...props} />}
    </>
  );
};
