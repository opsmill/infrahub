import { constructPathForIpam } from "@/entities/ipam/common/utils";
import { IPAM_QSP, IPAM_ROUTE, IPAM_TABS } from "@/entities/ipam/constants";
import { useGetIpNamespaceList } from "@/entities/ipam/namespaces/domain/get-ip-namespace-list.query";
import { NodeCore } from "@/entities/nodes/types";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { atom, useAtom } from "jotai";
import React from "react";
import { useNavigate, useParams } from "react-router";
import { StringParam, useQueryParam } from "use-query-params";

export const currentIpNamespaceAtom = atom<NodeCore>(undefined as unknown as NodeCore);

export function IpNamespaceProvider({ children }: { children: React.ReactNode }) {
  const [currentIpNamespace, setCurrentIpNamespace] = useAtom(currentIpNamespaceAtom);
  const [namespaceQSP] = useQueryParam(IPAM_QSP.NAMESPACE, StringParam);
  const { data, error, isPending } = useGetIpNamespaceList();

  React.useEffect(() => {
    if (!data) return;
    const flatData = data.pages.flat();
    const defaultNamespace = flatData.find((namespace) => {
      if (namespaceQSP) return namespace.id === namespaceQSP;
      return !!namespace.default?.value;
    });

    if (!defaultNamespace) return;
    setCurrentIpNamespace(defaultNamespace as unknown as NodeCore);
  }, [data]);

  if (isPending) {
    return <LoadingIndicator className="w-full h-full" />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  if (!currentIpNamespace) {
    return <LoadingIndicator className="w-full h-full" />;
  }

  return children;
}

export function useCurrentIpNamespace() {
  const { prefix, ip_address } = useParams();
  const [ipamTab] = useQueryParam(IPAM_QSP.TAB, StringParam);
  const navigate = useNavigate();
  const [_, setNamespaceQSP] = useQueryParam(IPAM_QSP.NAMESPACE, StringParam);
  const [currentIpNamespace, setCurrentIpNamespace] = useAtom(currentIpNamespaceAtom);

  const handleSetCurrentIpNamespace = React.useCallback((newValue: NodeCore) => {
    setCurrentIpNamespace(newValue);
    if (!newValue.id || newValue.id === currentIpNamespace?.id || newValue?.default?.value) {
      setNamespaceQSP(undefined); // Removes QSP for default namespace
    } else {
      setNamespaceQSP(newValue.id);
    }

    if (prefix || ip_address) {
      // Redirects to main lists on namespace switch
      if (ipamTab === IPAM_TABS.IP_DETAILS) {
        // Redirects to main IP Addresses view
        navigate(constructPathForIpam(IPAM_ROUTE.ADDRESSES));
      } else {
        // Redirects to main Prefixes view
        navigate(constructPathForIpam(IPAM_ROUTE.PREFIXES));
      }
    }
  }, []);

  if (!currentIpNamespace) {
    throw new Error("useCurrentIpNamespace must be use within IpNamespaceProvider");
  }

  return { currentIpNamespace, setCurrentIpNamespace: handleSetCurrentIpNamespace };
}
