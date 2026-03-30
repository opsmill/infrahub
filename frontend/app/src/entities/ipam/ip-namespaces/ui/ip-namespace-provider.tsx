import { CornerDownLeftIcon } from "lucide-react";
import { useQueryState } from "nuqs";
import React from "react";
import { Link, matchPath, useNavigate, useParams } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { Col } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { IP_ADDRESS_GENERIC, IPAM_QSP } from "@/entities/ipam/constants";
import { useGetIpNamespace } from "@/entities/ipam/ip-namespaces/domain/get-ip-namespace.query";
import type { IpNamespace } from "@/entities/ipam/ip-namespaces/domain/get-ip-namespace-list";
import { constructPathForIpam } from "@/entities/ipam/utils";
import type { NodeObject } from "@/entities/nodes/types";
import { getSchema } from "@/entities/schema/domain/get-schema";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

type IpNamespaceContext = {
  currentIpNamespace: NodeObject;
  setCurrentIpNamespace: (newIpNamespace: IpNamespace) => void;
};

export const IpNamespaceContext = React.createContext<IpNamespaceContext | null>(null);

export function IpNamespaceProvider({ children }: { children: React.ReactNode }) {
  const { objectKind } = useParams();
  const navigate = useNavigate();
  const [namespaceQSP] = useQueryState(IPAM_QSP.NAMESPACE);

  const {
    data: currentIpNamespace,
    isPending,
    error,
  } = useGetIpNamespace({ ipNamespaceId: namespaceQSP });

  if (isPending) {
    return <LoadingIndicator className="h-full" message="Loading IP namespaces..." />;
  }

  if (error || !currentIpNamespace) {
    return (
      <ErrorScreen
        message={
          <Col className="items-center">
            <span>{error?.message ?? `IP Namespace ${namespaceQSP ?? "default"} not found.`}</span>
            <Link
              to={constructPath("/ipam")}
              className="inline-flex items-center gap-2 text-indigo-700 hover:underline"
            >
              Go to default IP namespace <CornerDownLeftIcon className="size-4" />
            </Link>
          </Col>
        }
      />
    );
  }

  return (
    <IpNamespaceContext.Provider
      value={{
        currentIpNamespace,
        setCurrentIpNamespace: (newIpNamespace) => {
          const newIpNamespaceId = newIpNamespace.default?.value ? null : newIpNamespace.id;

          const isViewingIpAddress = objectKind
            ? (() => {
                const { schema } = getSchema(objectKind);
                return !!schema && isOfKind(IP_ADDRESS_GENERIC, schema);
              })()
            : !!matchPath("/ipam/ip_addresses", window.location.pathname);

          const basePath = isViewingIpAddress ? "/ipam/ip_addresses" : "/ipam";

          navigate(
            constructPathForIpam(basePath, [
              newIpNamespaceId
                ? { name: IPAM_QSP.NAMESPACE, value: newIpNamespaceId }
                : { name: IPAM_QSP.NAMESPACE, exclude: true },
            ])
          );
        },
      }}
    >
      {children}
    </IpNamespaceContext.Provider>
  );
}

export function useCurrentIpNamespace() {
  const context = React.use(IpNamespaceContext);

  if (!context) {
    throw new Error("useCurrentIpNamespace must be use within IpNamespaceProvider");
  }

  return context;
}
