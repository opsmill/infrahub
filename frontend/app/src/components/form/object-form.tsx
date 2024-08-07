import NoDataFound from "@/screens/errors/no-data-found";
import { DynamicFormProps } from "@/components/form/dynamic-form";
import { AttributeType, RelationshipType } from "@/utils/getObjectItemDisplayValue";
import { useSchema } from "@/hooks/useSchema";
import { GenericObjectForm } from "@/components/form/generic-object-form";
import { NodeWithProfileForm } from "@/components/form/node-with-profile-form";
import { NodeForm, NodeFormSubmitParams } from "@/components/form/node-form";
import { NUMBER_POOL_OBJECT } from "@/config/constants";
import { NumberPoolForm } from "@/screens/resource-manager/number-pool-form";

export type ProfileData = {
  [key: string]: string | Pick<AttributeType, "value" | "__typename">;
  display_label: string;
  id: string;
  __typename: string;
};

export interface ObjectFormProps extends Omit<DynamicFormProps, "fields" | "onSubmit"> {
  kind: string;
  onSuccess?: (newObject: any) => void;
  currentObject?: Record<string, AttributeType | RelationshipType>;
  currentProfiles?: ProfileData[];
  isFilterForm?: boolean;
  onSubmit?: (data: NodeFormSubmitParams) => void;
}

const ObjectForm = ({ kind, isFilterForm, currentProfiles, ...props }: ObjectFormProps) => {
  const { schema, isNode, isGeneric } = useSchema(kind);

  if (!schema) {
    return (
      <NoDataFound
        message={`Unable to generate the form. We couldn't find a schema for the kind "${kind}". Please check if the kind is correct or contact support if this issue persists.`}
      />
    );
  }

  if (isFilterForm) {
    return <NodeForm schema={schema} isFilterForm={isFilterForm} {...props} />;
  }

  if (isGeneric) {
    return <GenericObjectForm genericSchema={schema} {...props} />;
  }

  if (isNode && schema.generate_profile) {
    return (
      <NodeWithProfileForm
        schema={schema}
        isFilterForm={isFilterForm}
        profiles={currentProfiles}
        {...props}
      />
    );
  }

  if (kind === NUMBER_POOL_OBJECT) {
    return <NumberPoolForm />;
  }

  return (
    <NodeForm schema={schema} isFilterForm={isFilterForm} profiles={currentProfiles} {...props} />
  );
};

export default ObjectForm;
