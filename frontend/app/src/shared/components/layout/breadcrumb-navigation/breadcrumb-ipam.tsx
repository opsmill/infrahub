import { keepPreviousData } from "@tanstack/react-query";
import type React from "react";
import { useParams } from "react-router";

import {
  BreadcrumbItem,
  BreadcrumbItemError,
  BreadcrumbItemLoading,
  Breadcrumbs,
} from "@/shared/components/aria/breadcrumbs";
import { BreadcrumbObjectDetailsHierarchy } from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-object-details-hierarchy";
import { BreadcrumbItemObject } from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-item-object";

import {
  IP_ADDRESS_GENERIC,
  IP_PREFIX_GENERIC,
  IP_PREFIX_RELATIONSHIP_NAME,
} from "@/entities/ipam/constants";
import { constructPathForIpam } from "@/entities/ipam/utils";
import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import type { NodeRelationshipOne } from "@/entities/nodes/types";
import type { ModelSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

export function BreadcrumbIpam() {
  const { objectKind, objectId } = useParams();
  const { schema } = useSchema(objectKind);

  if (!schema || !objectId) return <BreadcrumbIpamBase />;

  return (
    <BreadcrumbIpamBase>
      <BreadcrumbIpamContent objectSchema={schema} objectId={objectId} />
    </BreadcrumbIpamBase>
  );
}

export function BreadcrumbIpamBase({ children }: { children?: React.ReactNode }) {
  return (
    <Breadcrumbs data-testid="breadcrumb-ipam">
      <BreadcrumbItem href={constructPathForIpam("/ipam")}>IP Address Manager</BreadcrumbItem>
      {children}
    </Breadcrumbs>
  );
}

interface BreadcrumbIpamContentProps {
  objectSchema: ModelSchema;
  objectId: string;
}

function BreadcrumbIpamContent({ objectSchema, objectId }: BreadcrumbIpamContentProps) {
  if (isOfKind(IP_PREFIX_GENERIC, objectSchema)) {
    return <BreadcrumbObjectDetailsHierarchy objectSchema={objectSchema} objectId={objectId} />;
  }

  if (isOfKind(IP_ADDRESS_GENERIC, objectSchema)) {
    return <BreadcrumbIpAddress ipAddressSchema={objectSchema} ipAddressId={objectId} />;
  }

  return null;
}

interface BreadcrumbIpAddressProps {
  ipAddressSchema: ModelSchema;
  ipAddressId: string;
}

export function BreadcrumbIpAddress({ ipAddressSchema, ipAddressId }: BreadcrumbIpAddressProps) {
  const { schema: ipPrefixSchema } = useSchema(IP_PREFIX_GENERIC);
  const { data, isPending, error } = useGetObject(
    {
      objectSchema: ipAddressSchema,
      objectId: ipAddressId,
    },
    {
      placeholderData: keepPreviousData,
    }
  );

  if (isPending) {
    return <BreadcrumbItemLoading />;
  }

  if (error) {
    return <BreadcrumbItemError error={error} />;
  }

  const ipPrefixRelationshipSchema = ipAddressSchema.relationships?.find(
    ({ name }) => name === IP_PREFIX_RELATIONSHIP_NAME
  );
  const ipPrefixNode = (data.ip_prefix as NodeRelationshipOne | undefined)?.node;

  return (
    <>
      {ipPrefixSchema && ipPrefixNode && (
        <BreadcrumbObjectDetailsHierarchy
          objectSchema={ipPrefixSchema}
          objectId={ipPrefixNode.id}
        />
      )}
      <BreadcrumbItemObject
        node={data}
        parentId={ipPrefixNode?.id}
        parentRelationshipSchema={ipPrefixRelationshipSchema}
      />
    </>
  );
}
