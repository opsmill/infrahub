import { useAtom } from "jotai";
import { useState } from "react";
import { StringParam, useQueryParam } from "use-query-params";
import { Select } from "../../components/inputs/select";
import { Skeleton } from "../../components/skeleton";
import { GET_NAMESPACES } from "../../graphql/queries/ipam/namespaces";
import useQuery from "../../hooks/useQuery";
import { defaultNamespaceAtom } from "../../state/atoms/namespace.atom";
import { IPAM_QSP, NAMESPACE_GENERIC } from "./constants";

export default function NamespaceSelector() {
  const [namespace, setNamespace] = useQueryParam(IPAM_QSP.NAMESPACE, StringParam);
  const [defaultNamespaceState, setDefaultNamespaceState] = useAtom(defaultNamespaceAtom);
  const [value, setValue] = useState(namespace ?? "");

  const { loading, data } = useQuery(GET_NAMESPACES);

  const handleNamespaceChange = (newValue: string) => {
    setValue(newValue);

    if (!newValue || newValue === defaultNamespaceState) {
      // Removes QSP for default namespace
      return setNamespace(undefined);
    }

    return setNamespace(newValue);
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
