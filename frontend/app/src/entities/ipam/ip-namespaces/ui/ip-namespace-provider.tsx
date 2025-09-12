import { atom, useAtom } from "jotai";
import { CornerDownLeftIcon } from "lucide-react";
import React from "react";
import { Link, useNavigate, useParams } from "react-router";
import { StringParam, useQueryParam } from "use-query-params";

import { constructPath } from "@/shared/api/rest/fetch";
import { Col } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { IP_ADDRESS_GENERIC, IPAM_QSP } from "@/entities/ipam/constants";
import { IpNamespace } from "@/entities/ipam/ip-namespaces/domain/get-ip-namespace-list";
import { useGetIpNamespaceList } from "@/entities/ipam/ip-namespaces/domain/get-ip-namespace-list.query";
import { constructPathForIpam } from "@/entities/ipam/utils";
import { NodeCore } from "@/entities/nodes/types";
import { getSchema } from "@/entities/schema/domain/get-schema";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

export const currentIpNamespaceAtom = atom<NodeCore>(undefined as unknown as NodeCore);

export function IpNamespaceProvider({ children }: { children: React.ReactNode }) {
  const [currentIpNamespace, setCurrentIpNamespace] = useAtom(currentIpNamespaceAtom);
  const [namespaceQSP] = useQueryParam(IPAM_QSP.NAMESPACE, StringParam);
  const { data, error, isPending } = useGetIpNamespaceList();
  const namespaceList = React.useMemo(() => data?.pages.flat() ?? [], [data]);

  React.useEffect(() => {
    if (!data) return;
    const selectedNamespace = namespaceList.find((namespace) => {
      if (namespaceQSP) return namespace.id === namespaceQSP;
      return !!namespace.default?.value;
    });

    if (!selectedNamespace) setCurrentIpNamespace(undefined!);
    setCurrentIpNamespace(selectedNamespace as unknown as NodeCore);
  }, [namespaceList, namespaceQSP]);

  if (isPending) {
    return <LoadingIndicator className="h-full" message="Loading IP namespaces..." />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  if (!currentIpNamespace) {
    return (
      <ErrorScreen
        message={
          <Col className="items-center">
            <span>{`IP Namespace ${namespaceQSP ?? "default"} not found.`}</span>
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

  return children;
}

export function useCurrentIpNamespace() {
  const { objectKind } = useParams();
  const navigate = useNavigate();
  const [_, setNamespaceQSP] = useQueryParam(IPAM_QSP.NAMESPACE, StringParam);
  const [currentIpNamespace, setCurrentIpNamespace] = useAtom(currentIpNamespaceAtom);

  const handleSetCurrentIpNamespace = React.useCallback(
    (newValue: IpNamespace) => {
      setCurrentIpNamespace(newValue);
      if (!newValue.id || newValue.id === currentIpNamespace?.id || newValue?.default?.value) {
        setNamespaceQSP(undefined); // Removes QSP for default namespace
      } else {
        setNamespaceQSP(newValue.id);
      }

      if (!objectKind) return;

      const { schema } = getSchema(objectKind);
      const isViewingIpAddress = !!schema && isOfKind(IP_ADDRESS_GENERIC, schema);
      navigate(constructPathForIpam(isViewingIpAddress ? "/ipam/ip_addresses" : "/ipam"));
    },
    [objectKind]
  );

  if (!currentIpNamespace) {
    throw new Error("useCurrentIpNamespace must be use within IpNamespaceProvider");
  }

  return { currentIpNamespace, setCurrentIpNamespace: handleSetCurrentIpNamespace };
}
