import NoDataFound from "@/screens/errors/no-data-found";
import { DynamicFormProps } from "@/components/form/dynamic-form";
import { AttributeType, RelationshipType } from "@/utils/getObjectItemDisplayValue";
import { useSchema } from "@/hooks/useSchema";
import { GenericObjectForm } from "@/components/form/generic-object-form";
import { NodeWithProfileForm } from "@/components/form/node-with-profile-form";
import { NodeForm, NodeFormSubmitParams } from "@/components/form/node-form";
import { NUMBER_POOL_OBJECT, READONLY_REPOSITORY_KIND, REPOSITORY_KIND } from "@/config/constants";
import { NumberPoolForm } from "@/screens/resource-manager/number-pool-form";
import { lazy, Suspense } from "react";
import LoadingScreen from "@/screens/loading-screen/loading-screen";

export type ProfileData = {
  [key: string]: string | Pick<AttributeType, "value" | "__typename">;
  display_label: string;
  id: string;
  __typename: string;
};

const RepositoryForm = lazy(() => import("@/screens/repository/repository-form"));

export interface ObjectFormProps extends Omit<DynamicFormProps, "fields" | "onSubmit"> {
  kind: string;
  onSuccess?: (newObject: any) => void;
  currentObject?: Record<string, AttributeType | RelationshipType>;
  currentProfiles?: ProfileData[];
  isFilterForm?: boolean;
  onSubmit?: (data: NodeFormSubmitParams) => void;
  onUpdateComplete?: () => void;
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

  if ([REPOSITORY_KIND, READONLY_REPOSITORY_KIND].includes(kind)) {
    return (
      <Suspense fallback={<LoadingScreen hideText className="mt-4" />}>
        <RepositoryForm schema={schema} {...props} />
      </Suspense>
    );
  }

  if (kind === NUMBER_POOL_OBJECT) {
    return <NumberPoolForm {...props} />;
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

  return (
    <NodeForm schema={schema} isFilterForm={isFilterForm} profiles={currentProfiles} {...props} />
  );
};

export default ObjectForm;
