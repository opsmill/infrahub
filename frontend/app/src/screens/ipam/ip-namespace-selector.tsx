import { Select, SelectOption } from "@/components/inputs/select";
import { Skeleton } from "@/components/skeleton";
import { GET_IP_NAMESPACES } from "@/graphql/queries/ipam/ip-namespaces";
import useQuery from "@/hooks/useQuery";
import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { defaultIpNamespaceAtom } from "./common/namespace.state";
import { constructPathForIpam } from "./common/utils";
import { IPAM_QSP, IPAM_ROUTE, IPAM_TABS, NAMESPACE_GENERIC } from "./constants";

export default function IpNamespaceSelector() {
  const { loading, data, error } = useQuery(GET_IP_NAMESPACES);

  if (loading) {
    return <Skeleton className="h-10 w-80" />;
  }

  if (error) {
    return null;
  }

  const namespaces = data?.[NAMESPACE_GENERIC]?.edges.map((edge: any) => edge.node) ?? [];
  const defaultNamespace = namespaces.find((result: any) => result.default?.value === true);

  return <IpNamespaceSelectorContent namespaces={namespaces} defaultNamespace={defaultNamespace} />;
}

type IpNamespaceSelectorContentProps = {
  namespaces: Array<any>;
  defaultNamespace: any;
};

const IpNamespaceSelectorContent = ({
  namespaces,
  defaultNamespace,
}: IpNamespaceSelectorContentProps) => {
  const { prefix, ip_address } = useParams();
  const navigate = useNavigate();
  const [ipamTab] = useQueryParam(IPAM_QSP.TAB, StringParam);
  const [namespaceQSP, setNamespaceQSP] = useQueryParam(IPAM_QSP.NAMESPACE, StringParam);
  const [defaultIpNamespace, setDefaultIpNamespace] = useAtom(defaultIpNamespaceAtom);

  useEffect(() => {
    setDefaultIpNamespace(defaultNamespace.id);
  }, []);

  const handleNamespaceChange = (newValue: SelectOption) => {
    if (!newValue?.id || newValue?.id === defaultIpNamespace) {
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
  };

  return (
    <div className="flex gap-2 items-center">
      <Icon icon="mdi:chevron-right" />
      <span>Namespace</span>
      <Select
        value={namespaceQSP ?? defaultNamespace.id}
        onChange={handleNamespaceChange}
        options={namespaces.map((option) => ({
          id: option.id,
          name: option.display_label,
          description: option.description?.value,
        }))}
        data-testid="namespace-select"
        preventEmpty
      />
    </div>
  );
};
