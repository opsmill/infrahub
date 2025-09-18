import { useState } from "react";

import NoDataFound from "@/shared/components/errors/no-data-found";
import { GenericSelector } from "@/shared/components/form/generic-selector";
import ObjectForm, { type ObjectFormProps } from "@/shared/components/form/object-form";

import type { GenericSchema } from "@/entities/schema/types";

interface GenericObjectFormProps extends Omit<ObjectFormProps, "kind"> {
  genericSchema: GenericSchema;
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

      {kindToCreate && <ObjectForm key={kindToCreate} kind={kindToCreate} {...props} />}
    </>
  );
};
