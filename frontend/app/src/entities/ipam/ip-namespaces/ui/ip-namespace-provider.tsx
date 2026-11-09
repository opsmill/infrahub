import { CornerDownLeftIcon } from "lucide-react";
import { useQueryState } from "nuqs";
import React from "react";
import { Link, matchPath, useNavigate, useParams } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { Col } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { QSP } from "@/shared/config/qsp";

import { IP_ADDRESS_GENERIC } from "@/entities/ipam/ip-addresses/domain/model/ip-address";
import type { IpNamespace } from "@/entities/ipam/ip-namespaces/domain/use-cases/get-ip-namespace-list";
import { useGetIpNamespace } from "@/entities/ipam/ip-namespaces/ui/queries/get-ip-namespace.query";
import { constructPathForIpam } from "@/entities/ipam/ip-namespaces/ui/routing/ipam-urls";
import type { NodeObject } from "@/entities/nodes/object/domain/model/node";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";
import { getSchema } from "@/entities/schema/domain/use-cases/get-schema";

type IpNamespaceContext = {
  currentIpNamespace: NodeObject;
  setCurrentIpNamespace: (newIpNamespace: IpNamespace) => void;
};

export const IpNamespaceContext = React.createContext<IpNamespaceContext | null>(null);

export function IpNamespaceProvider({ children }: { children: React.ReactNode }) {
  const { objectKind } = useParams();
  const navigate = useNavigate();
  const [namespaceQSP] = useQueryState(QSP.IPAM_NAMESPACE);

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
                ? { name: QSP.IPAM_NAMESPACE, value: newIpNamespaceId }
                : { name: QSP.IPAM_NAMESPACE, exclude: true },
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
