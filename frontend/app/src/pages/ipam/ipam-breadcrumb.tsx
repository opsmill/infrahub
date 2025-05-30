import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { constructPathForIpam } from "@/entities/ipam/common/utils";
import { IP_ADDRESS_GENERIC, IP_PREFIX_GENERIC } from "@/entities/ipam/constants";
import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { isRelationshipVisibleInDetailedView } from "@/entities/nodes/object/utils/get-relationships-visible-in-detailed-view";
import { NodeCore, NodeObject, NodeRelationshipOne } from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { ModelSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { Spinner } from "@/shared/components/ui/spinner";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { gql } from "@apollo/client";
import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { jsonToGraphQLQuery } from "json-to-graphql-query";
import { ChevronRightIcon, HouseIcon } from "lucide-react";
import { Link, LinkProps, useParams } from "react-router";
import { classNames } from "@/shared/utils/common";

interface IPPrefixNode extends NodeCore {
  parent?: {
    node: { id: string } | null;
  };
  ip_namespace?: {
    node: {
      id: string;
      display_label: string;
      hfid: string;
    };
  };
}

function useGetIpPrefixAncestors(objectKind: string, objectId: string) {
  const { currentBranch } = useCurrentBranch();
  const atDate = useAtomValue(datetimeAtom);

  return useQuery({
    queryKey: ["objects", objectKind, objectId, "ancestors"],
    queryFn: async (): Promise<IPPrefixNode[]> => {
      const query = buildGetAncestorsQuery(objectKind, objectId);

      const { data } = await graphqlClient.query({
        query: gql(query),
        context: {
          branch: currentBranch.name,
          date: atDate,
        },
      });

      const result = data[objectKind]?.edges?.map((edge: { node: NodeObject }) => edge.node) ?? [];

      if (!result || result.length === 0) {
        throw new Error(`Cannot find ${objectKind} with id ${objectId}`);
      }

      const { ancestors, ...currentObject } = result[0];
      return [
        currentObject as IPPrefixNode,
        ...(ancestors?.edges?.map((edge: { node: NodeObject }) => edge.node) ?? []),
      ];
    },
  });
}

function buildGetAncestorsQuery(objectKind: string, objectId: string): string {
  return jsonToGraphQLQuery({
    query: {
      __name: `Get${objectKind}Ancestors`,
      [objectKind]: {
        __args: {
          ids: [objectId],
        },
        edges: {
          node: {
            id: true,
            hfid: true,
            display_label: true,
            __typename: true,
            parent: {
              node: { id: true },
            },
            ip_namespace: {
              node: {
                id: true,
                display_label: true,
                hfid: true,
              },
            },
            ancestors: {
              edges: {
                node: {
                  id: true,
                  hfid: true,
                  display_label: true,
                  __typename: true,
                  parent: {
                    node: { id: true },
                  },
                },
              },
            },
          },
        },
      },
    },
  });
}

function BreadcrumbError({ error }: { error: Error }) {
  console.error("IPAM Breadcrumb Error:", error);

  return (
    <div className="text-red-500 text-sm flex items-center gap-1">
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
    <Link className={classNames("last:font-medium last:text-neutral-600", className)} {...props} />
  );
}

export function IpamBreadcrumb() {
  return (
    <nav
      className="text-neutral-400 text-sm flex items-center gap-1 h-9"
      aria-label="IPAM navigation breadcrumb"
    >
      <Link to={constructPathForIpam("/ipam")} aria-label="Navigate to IPAM home">
        <HouseIcon className="size-4" />
      </Link>

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
  const { data: ancestors, isPending, error } = useGetIpPrefixAncestors(objectKind, objectId);

  if (isPending) {
    return <IpamBreadcrumbLoading />;
  }

  if (error) {
    return <BreadcrumbError error={error} />;
  }

  if (!ancestors || ancestors.length === 0) {
    return null;
  }

  return <RecursiveAncestorBreadcrumb ancestors={ancestors} currentObjectId={objectId} />;
}

interface RecursiveAncestorBreadcrumbProps {
  ancestors: IPPrefixNode[];
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
