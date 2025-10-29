import { ChevronRightIcon, HouseIcon } from "lucide-react";
import type React from "react";
import { Link, type LinkProps, useParams } from "react-router";

import { Spinner } from "@/shared/components/ui/spinner";
import { focusVisibleStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import { IP_ADDRESS_GENERIC, IP_PREFIX_GENERIC } from "@/entities/ipam/constants";
import { constructPathForIpam } from "@/entities/ipam/utils";
import { useGetObjectAncestors } from "@/entities/nodes/hierarchy/domain/get-object-ancestors.query";
import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { isRelationshipVisibleInDetailedView } from "@/entities/nodes/object/utils/get-relationships-visible-in-detailed-view";
import type { NodeCoreWithParent, NodeRelationshipOne } from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import type { ModelSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

function BreadcrumbError({ error }: { error: Error }) {
  console.error("IPAM Breadcrumb Error:", error);

  return (
    <div className="flex items-center text-red-500 text-sm">
      <IpamBreadcrumbSeparator />
      <span>Error loading breadcrumb</span>
    </div>
  );
}

function IpamBreadcrumbSeparator() {
  return <ChevronRightIcon className="size-3.5" />;
}

function IpamBreadcrumbLoading() {
  return (
    <>
      <IpamBreadcrumbSeparator />
      <Spinner />
    </>
  );
}

function IpamBreadcrumbLink({ className, ...props }: LinkProps) {
  return (
    <Link
      className={classNames(
        focusVisibleStyle,
        "rounded-md border border-transparent p-1",
        "last:font-medium last:text-neutral-600 hover:text-neutral-600",
        className
      )}
      {...props}
    />
  );
}

export interface IpamBreadcrumbProps extends React.HTMLAttributes<HTMLDivElement> {}

export function IpamBreadcrumb({ className, ...props }: IpamBreadcrumbProps) {
  return (
    <nav
      className={classNames("flex items-center text-neutral-400 text-sm", className)}
      aria-label="IPAM navigation breadcrumb"
      {...props}
    >
      <IpamBreadcrumbLink to={constructPathForIpam("/ipam")} aria-label="Navigate to IPAM home">
        <HouseIcon className="size-4" />
      </IpamBreadcrumbLink>

      <IPAMBreadcrumbContent />
    </nav>
  );
}

export function IPAMBreadcrumbContent() {
  const { objectKind, objectId } = useParams<{ objectKind: string; objectId: string }>();
  const { schema } = useSchema(objectKind);

  const IpamRoot = <span className="ml-1">IPAM</span>;

  if (!objectKind || !objectId) {
    return IpamRoot;
  }

  if (schema && isOfKind(IP_PREFIX_GENERIC, schema)) {
    return <IpPrefixHierarchyBreadcrumb objectKind={objectKind} objectId={objectId} />;
  }

  if (schema && isOfKind(IP_ADDRESS_GENERIC, schema)) {
    return <IpAddressBreadcrumb objectSchema={schema} objectId={objectId} />;
  }

  return IpamRoot;
}

interface IpPrefixHierarchyBreadcrumbProps {
  objectKind: string;
  objectId: string;
}

function IpPrefixHierarchyBreadcrumb({ objectKind, objectId }: IpPrefixHierarchyBreadcrumbProps) {
  const { data, isPending, error } = useGetObjectAncestors({ objectKind, objectId });

  if (isPending) {
    return <IpamBreadcrumbLoading />;
  }

  if (error) {
    return <BreadcrumbError error={error} />;
  }

  if (!data || data.length === 0) {
    return null;
  }

  return <RecursiveAncestorBreadcrumb ancestors={data} currentObjectId={objectId} />;
}

interface RecursiveAncestorBreadcrumbProps {
  ancestors: NodeCoreWithParent[];
  currentObjectId?: string;
}

function RecursiveAncestorBreadcrumb({
  ancestors,
  currentObjectId,
}: RecursiveAncestorBreadcrumbProps) {
  if (!currentObjectId) {
    return null;
  }

  const currentObject = ancestors.find((node) => node.id === currentObjectId);

  if (!currentObject) {
    return null;
  }

  const parentId = currentObject.parent?.node?.id;

  return (
    <>
      {parentId && <RecursiveAncestorBreadcrumb ancestors={ancestors} currentObjectId={parentId} />}

      <IpamBreadcrumbSeparator />

      <IpamBreadcrumbLink to={getObjectDetailsUrl(currentObject.__typename, currentObject.id)}>
        {currentObject.display_label}
      </IpamBreadcrumbLink>
    </>
  );
}

interface IpAddressBreadcrumbProps {
  objectSchema: ModelSchema;
  objectId: string;
}

function IpAddressBreadcrumb({ objectSchema, objectId }: IpAddressBreadcrumbProps) {
  const { data, isPending, error } = useGetObject({
    objectSchema,
    objectId,
    getRelationshipsVisible: (relationships) =>
      relationships.filter((rel) => {
        if (rel.cardinality === "one") return true;
        return isRelationshipVisibleInDetailedView(rel);
      }),
  });

  if (isPending) {
    return <IpamBreadcrumbLoading />;
  }

  if (error) {
    return <BreadcrumbError error={error} />;
  }

  const ipPrefix = data.ip_prefix as NodeRelationshipOne | undefined;

  return (
    <>
      {ipPrefix?.node && (
        <IpPrefixHierarchyBreadcrumb
          objectKind={ipPrefix.node.__typename}
          objectId={ipPrefix.node.id}
        />
      )}

      <IpamBreadcrumbSeparator />

      <IpamBreadcrumbLink to={getObjectDetailsUrl(data.__typename, data.id)}>
        {data.display_label}
      </IpamBreadcrumbLink>
    </>
  );
}
