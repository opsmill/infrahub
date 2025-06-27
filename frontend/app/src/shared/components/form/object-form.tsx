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
import { NodeObject } from "@/entities/nodes/types";
import { IP_ADDRESS_POOL, IP_PREFIX_POOL } from "@/entities/resource-manager/constants";
import { IpAddressPoolForm } from "@/entities/resource-manager/ui/ip-address-pool-form";
import { IpPrefixPoolForm } from "@/entities/resource-manager/ui/ip-prefix-pool-form";
import { NumberPoolForm } from "@/entities/resource-manager/ui/number-pool-form";
import { AccountForm } from "@/entities/role-manager/ui/account-form";
import { AccountGroupForm } from "@/entities/role-manager/ui/account-group-form";
import { AccountRoleForm } from "@/entities/role-manager/ui/account-role-form";
import { GlobalPermissionForm } from "@/entities/role-manager/ui/global-permissions-form";
import { ObjectPermissionForm } from "@/entities/role-manager/ui/object-permissions-form";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { getTemplateRelationshipFromSchema } from "@/entities/schema/utils/get-template-relationship-from-schema";
import {
  NODE_TRIGGER_ATTRIBUTE_MATCH,
  NODE_TRIGGER_RELATIONSHIP_MATCH,
} from "@/entities/triggers/constants";
import { NodeAttributeMatchForm } from "@/entities/triggers/ui/node-attribute-match-form";
import { NodeRelationshipMatchForm } from "@/entities/triggers/ui/node-relationship-match-form";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { DynamicFormProps } from "@/shared/components/form/dynamic-form";
import { GenericObjectForm } from "@/shared/components/form/generic-object-form";
import { NodeForm, NodeFormSubmitParams } from "@/shared/components/form/node-form";
import { NodeWithProfileForm } from "@/shared/components/form/node-with-profile-form";
import { useCurrentFormContext } from "@/shared/components/form/utils/form-context";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Suspense, lazy } from "react";

export type ProfileData = {
  [key: string]: string | Pick<AttributeType, "value" | "__typename">;
  display_label: string;
  id: string;
  __typename: string;
};

const RepositoryForm = lazy(() => import("@/entities/repository/ui/repository-form"));
const ObjectTemplateForm = lazy(
  () => import("@/entities/nodes/object-template/object-template-form")
);

export interface ObjectFormProps extends Omit<DynamicFormProps, "fields" | "onSubmit"> {
  kind: string;
  onSuccess?: (newObject: any) => void;
  currentObject?: Record<string, AttributeType | RelationshipType>;
  objectTemplate?: NodeObject | null;
  currentProfiles?: ProfileData[];
  isUpdate?: boolean;
  onSubmit?: (data: NodeFormSubmitParams) => void;
}

const ObjectForm = ({ kind, currentProfiles, ...props }: ObjectFormProps) => {
  const { schema, isNode, isGeneric } = useSchema(kind);
  const { parentSchema, parentData } = useCurrentFormContext();

  if (!schema) {
    return (
      <NoDataFound
        message={`Unable to generate the form. We couldn't find a schema for the kind "${kind}". Please check if the kind is correct or contact support if this issue persists.`}
      />
    );
  }

  if (!props.isUpdate && !isGeneric) {
    const objectTemplateRelationship = getTemplateRelationshipFromSchema(schema);
    if (objectTemplateRelationship && props.objectTemplate === undefined) {
      return (
        <Suspense fallback={<LoadingIndicator className="mt-4" />}>
          <ObjectTemplateForm
            kind={kind}
            objectTemplateKind={objectTemplateRelationship.peer}
            {...props}
          />
        </Suspense>
      );
    }
  }

  if ([REPOSITORY_KIND, READONLY_REPOSITORY_KIND].includes(kind)) {
    return (
      <Suspense fallback={<LoadingIndicator className="mt-4" />}>
        <RepositoryForm
          schema={schema}
          parentSchema={parentSchema}
          parentData={parentData}
          {...props}
        />
      </Suspense>
    );
  }

  if (kind === NUMBER_POOL_OBJECT) {
    return <NumberPoolForm parentSchema={parentSchema} parentData={parentData} {...props} />;
  }

  if (kind === ACCOUNT_OBJECT) {
    return <AccountForm parentSchema={parentSchema} parentData={parentData} {...props} />;
  }

  if (kind === ACCOUNT_GROUP_OBJECT) {
    return <AccountGroupForm parentSchema={parentSchema} parentData={parentData} {...props} />;
  }

  if (kind === ACCOUNT_ROLE_OBJECT) {
    return <AccountRoleForm parentSchema={parentSchema} parentData={parentData} {...props} />;
  }

  if (kind === GLOBAL_PERMISSION_OBJECT) {
    return <GlobalPermissionForm parentSchema={parentSchema} parentData={parentData} {...props} />;
  }

  if (kind === OBJECT_PERMISSION_OBJECT) {
    return <ObjectPermissionForm parentSchema={parentSchema} parentData={parentData} {...props} />;
  }

  if (kind === IP_ADDRESS_POOL) {
    return (
      <IpAddressPoolForm
        schema={schema}
        parentSchema={parentSchema}
        parentData={parentData}
        {...props}
      />
    );
  }

  if (kind === IP_PREFIX_POOL) {
    return (
      <IpPrefixPoolForm
        schema={schema}
        parentSchema={parentSchema}
        parentData={parentData}
        {...props}
      />
    );
  }

  if (kind === NODE_TRIGGER_ATTRIBUTE_MATCH) {
    return (
      <NodeAttributeMatchForm
        schema={schema}
        parentSchema={parentSchema}
        parentData={parentData}
        {...props}
      />
    );
  }

  if (kind === NODE_TRIGGER_RELATIONSHIP_MATCH) {
    return (
      <NodeRelationshipMatchForm
        schema={schema}
        parentSchema={parentSchema}
        parentData={parentData}
        {...props}
      />
    );
  }

  if (isGeneric) {
    return (
      <GenericObjectForm
        genericSchema={schema}
        parentSchema={parentSchema}
        parentData={parentData}
        {...props}
      />
    );
  }

  if (isNode && schema.generate_profile) {
    return (
      <NodeWithProfileForm
        schema={schema}
        profiles={currentProfiles}
        parentSchema={parentSchema}
        parentData={parentData}
        {...props}
      />
    );
  }

  return (
    <NodeForm
      schema={schema}
      profiles={currentProfiles}
      parentSchema={parentSchema}
      parentData={parentData}
      {...props}
    />
  );
};

export default ObjectForm;
