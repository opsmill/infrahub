import {
  ACCOUNT_GROUP_OBJECT,
  ACCOUNT_OBJECT,
  ACCOUNT_ROLE_OBJECT,
  GLOBAL_PERMISSION_OBJECT,
  NUMBER_POOL_OBJECT,
  OBJECT_PERMISSION_OBJECT,
  READONLY_REPOSITORY_KIND,
  REPOSITORY_KIND,
} from "@/config/constants";
import { AttributeType, RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { NumberPoolForm } from "@/entities/resource-manager/number-pool-form";
import { AccountForm } from "@/entities/role-manager/account-form";
import { AccountGroupForm } from "@/entities/role-manager/account-group-form";
import { AccountRoleForm } from "@/entities/role-manager/account-role-form";
import { GlobalPermissionForm } from "@/entities/role-manager/global-permissions-form";
import { ObjectPermissionForm } from "@/entities/role-manager/object-permissions-form";
import { useSchema } from "@/entities/schema/useSchema";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { DynamicFormProps } from "@/shared/components/form/dynamic-form";
import { GenericObjectForm } from "@/shared/components/form/generic-object-form";
import { NodeForm, NodeFormSubmitParams } from "@/shared/components/form/node-form";
import { NodeWithProfileForm } from "@/shared/components/form/node-with-profile-form";
import LoadingScreen from "@/shared/components/loading-screen";
import { Suspense, lazy } from "react";

export type ProfileData = {
  [key: string]: string | Pick<AttributeType, "value" | "__typename">;
  display_label: string;
  id: string;
  __typename: string;
};

const RepositoryForm = lazy(() => import("@/entities/repository/repository-form"));

export interface ObjectFormProps extends Omit<DynamicFormProps, "fields" | "onSubmit"> {
  kind: string;
  onSuccess?: (newObject: any) => void;
  currentObject?: Record<string, AttributeType | RelationshipType>;
  currentProfiles?: ProfileData[];
  isUpdate?: boolean;
  onSubmit?: (data: NodeFormSubmitParams) => void;
  onUpdateComplete?: () => void;
}

const ObjectForm = ({ kind, currentProfiles, ...props }: ObjectFormProps) => {
  const { schema, isNode, isGeneric } = useSchema(kind);

  if (!schema) {
    return (
      <NoDataFound
        message={`Unable to generate the form. We couldn't find a schema for the kind "${kind}". Please check if the kind is correct or contact support if this issue persists.`}
      />
    );
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

  if (kind === ACCOUNT_OBJECT) {
    return <AccountForm {...props} />;
  }

  if (kind === ACCOUNT_GROUP_OBJECT) {
    return <AccountGroupForm {...props} />;
  }

  if (kind === ACCOUNT_ROLE_OBJECT) {
    return <AccountRoleForm {...props} />;
  }

  if (kind === GLOBAL_PERMISSION_OBJECT) {
    return <GlobalPermissionForm {...props} />;
  }

  if (kind === OBJECT_PERMISSION_OBJECT) {
    return <ObjectPermissionForm {...props} />;
  }

  if (isGeneric) {
    return <GenericObjectForm genericSchema={schema} {...props} />;
  }

  if (isNode && schema.generate_profile) {
    return <NodeWithProfileForm schema={schema} profiles={currentProfiles} {...props} />;
  }

  return <NodeForm schema={schema} profiles={currentProfiles} {...props} />;
};

export default ObjectForm;
