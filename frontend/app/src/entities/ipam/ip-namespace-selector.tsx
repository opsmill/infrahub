import { GET_IP_NAMESPACES } from "@/entities/ipam/api/ip-namespaces";
import { IpamNamespace } from "@/shared/api/graphql/generated/graphql";
import useQuery from "@/shared/api/graphql/useQuery";
import { constructPath } from "@/shared/api/rest/fetch";
import { LinkButton } from "@/shared/components/buttons/button-primitive";
import { Col } from "@/shared/components/container";
import { Skeleton } from "@/shared/components/skeleton";
import {
  Combobox,
  ComboboxContent,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";
import { Icon } from "@iconify-icon/react";
import { useSetAtom } from "jotai";
import { useEffect, useId } from "react";
import { useNavigate, useParams } from "react-router";
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

  return <IpNamespaceSelectorContent namespaces={namespaces} />;
}

type IpNamespaceSelectorContentProps = {
  namespaces: Array<IpamNamespace>;
};

const IpNamespaceSelectorContent = ({ namespaces }: IpNamespaceSelectorContentProps) => {
  const { prefix, ip_address } = useParams();
  const navigate = useNavigate();
  const [ipamTab] = useQueryParam(IPAM_QSP.TAB, StringParam);
  const [namespaceQSP, setNamespaceQSP] = useQueryParam(IPAM_QSP.NAMESPACE, StringParam);
  const setDefaultIpNamespace = useSetAtom(defaultIpNamespaceAtom);
  const selectedNamespace = namespaces.find((result) => result.id === namespaceQSP);
  const defaultNamespace = namespaces.find((result) => result.default?.value === true);
  const currentNamespace = selectedNamespace || defaultNamespace;
  const id = useId();

  useEffect(() => {
    if (defaultNamespace) {
      setDefaultIpNamespace(defaultNamespace.id);
    }
  }, []);

  const handleNamespaceChange = (newValue: IpamNamespace) => {
    if (!newValue.id || newValue.id === defaultNamespace?.id) {
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
      <label htmlFor={id}>Namespace</label>

      <Combobox>
        <ComboboxTrigger id={id} data-testid="namespace-select">
          {selectedNamespace?.display_label ?? defaultNamespace?.display_label}
        </ComboboxTrigger>

        <ComboboxContent align="start" fitTriggerWidth={false}>
          <ComboboxList className="max-w-md">
            {namespaces.map((namespace) => (
              <ComboboxItem
                key={namespace.id}
                value={namespace.id}
                selectedValue={currentNamespace?.id}
                onSelect={() => handleNamespaceChange(namespace)}
              >
                <div className="overflow-hidden">
                  <div className="truncate font-semibold">{namespace.display_label}</div>
                  <p className="text-xs truncate text-gray-500">{namespace.description?.value}</p>
                </div>
              </ComboboxItem>
            ))}
          </ComboboxList>
          <Col className="border-t border-neutral-200">
            <LinkButton
              to={constructPath("/ipam/namespaces")}
              variant="ghost"
              size="sm"
              className="text-xs justify-start m-2"
            >
              View all IP namespaces
            </LinkButton>
          </Col>
        </ComboboxContent>
      </Combobox>
    </div>
  );
};
