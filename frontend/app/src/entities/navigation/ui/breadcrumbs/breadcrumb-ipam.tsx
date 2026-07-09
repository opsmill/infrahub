import {
  BreadcrumbItem,
  BreadcrumbItemError,
  BreadcrumbItemLoading,
  Breadcrumbs,
} from "@infrahub/ui";
import { keepPreviousData } from "@tanstack/react-query";
import { useQueryState } from "nuqs";
import type React from "react";
import { useParams } from "react-router";

import { QSP } from "@/shared/config/qsp";

import { IP_ADDRESS_GENERIC } from "@/entities/ipam/ip-addresses/domain/model/ip-address";
import { constructPathForIpam } from "@/entities/ipam/ip-namespaces/ui/routing/ipam-urls";
import {
  IP_PREFIX_GENERIC,
  IP_PREFIX_RELATIONSHIP_NAME,
} from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix";
import { BreadcrumbObjectDetailsHierarchy } from "@/entities/navigation/ui/breadcrumbs/breadcrumb-object-details-hierarchy";
import { BreadcrumbItemObject } from "@/entities/navigation/ui/breadcrumbs/items/breadcrumb-item-object";
import type { NodeRelationshipOne } from "@/entities/nodes/object/domain/model/node";
import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";
import type { GetRelationshipsParams } from "@/entities/nodes/relationships/domain/use-cases/get-relationships";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

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
  const [namespaceQSP] = useQueryState(QSP.IPAM_NAMESPACE);
  const filterQuery = namespaceQSP ? { ip_namespace__ids: [namespaceQSP] } : undefined;

  if (isOfKind(IP_PREFIX_GENERIC, objectSchema)) {
    return (
      <BreadcrumbObjectDetailsHierarchy
        objectSchema={objectSchema}
        objectId={objectId}
        filterQuery={filterQuery}
      />
    );
  }

  if (isOfKind(IP_ADDRESS_GENERIC, objectSchema)) {
    return (
      <BreadcrumbIpAddress
        ipAddressSchema={objectSchema}
        ipAddressId={objectId}
        filterQuery={filterQuery}
      />
    );
  }

  return null;
}

interface BreadcrumbIpAddressProps {
  ipAddressSchema: ModelSchema;
  ipAddressId: string;
  filterQuery?: GetRelationshipsParams["filterQuery"];
}

export function BreadcrumbIpAddress({
  ipAddressSchema,
  ipAddressId,
  filterQuery,
}: BreadcrumbIpAddressProps) {
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
          filterQuery={filterQuery}
        />
      )}
      <BreadcrumbItemObject
        node={data}
        parentId={ipPrefixNode?.id}
        parentRelationshipSchema={ipPrefixRelationshipSchema}
        filterQuery={filterQuery}
      />
    </>
  );
}
