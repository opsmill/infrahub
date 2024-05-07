import { useAtom } from "jotai";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { Select } from "../../components/inputs/select";
import { Skeleton } from "../../components/skeleton";
import { GET_NAMESPACES } from "../../graphql/queries/ipam/namespaces";
import useQuery from "../../hooks/useQuery";
import { defaultNamespaceAtom } from "../../state/atoms/namespace.atom";
import { constructPath } from "../../utils/fetch";
import { IPAM_QSP, IPAM_ROUTE, IPAM_TABS, NAMESPACE_GENERIC } from "./constants";

export default function NamespaceSelector() {
  const navigate = useNavigate();
  const { prefix, ip_address } = useParams();
  const [namespace, setNamespace] = useQueryParam(IPAM_QSP.NAMESPACE, StringParam);
  const [ipamTab] = useQueryParam(IPAM_QSP.TAB, StringParam);
  const [defaultNamespaceState, setDefaultNamespaceState] = useAtom(defaultNamespaceAtom);
  const [value, setValue] = useState(namespace ?? "");

  const { loading, data } = useQuery(GET_NAMESPACES);

  const handleNamespaceChange = (newValue: string) => {
    setValue(newValue);

    if (!newValue || newValue === defaultNamespaceState) {
      // Removes QSP for default namespace
      setNamespace(undefined);
    } else {
      setNamespace(newValue);
    }

    if (prefix || ip_address) {
      // Redirects to main lists on namespace switch
      if (ipamTab === IPAM_TABS.IP_DETAILS) {
        // Redirects to main IP Adresses view
        navigate(
          constructPath(
            `${IPAM_ROUTE.ADDRESSES}/`,
            [{ name: IPAM_QSP.TAB, value: IPAM_TABS.IP_DETAILS }],
            [IPAM_QSP.NAMESPACE]
          )
        );
      } else {
        // Redirects to main Prefixes view
        navigate(constructPath(`${IPAM_ROUTE.PREFIXES}/`, [], [IPAM_QSP.NAMESPACE]));
      }
    }
  };

  const namespaces = (data && data[NAMESPACE_GENERIC]?.edges.map((edge) => edge.node)) ?? [];

  const defaultNamespace = namespaces.find((result) => result.default?.value);

  if (!value && defaultNamespace?.id) {
    // Store default namespace
    setValue(defaultNamespace.id);
  }

  if (defaultNamespace?.id && !defaultNamespaceState) {
    setDefaultNamespaceState(defaultNamespace.id);
  }

  const options = namespaces.map((option) => ({
    id: option.id,
    name: option.display_label,
    description: option.description?.value,
  }));

  if (loading) {
    return <Skeleton className="h-8 w-40" />;
  }

  return (
    <>
      <span className="mr-2">Namespace:</span>
      <Select value={value} onChange={handleNamespaceChange} options={options} preventEmpty />
    </>
  );
}
