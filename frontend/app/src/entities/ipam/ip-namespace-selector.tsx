import { GET_IP_NAMESPACES } from "@/entities/ipam/api/ip-namespaces";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { IpamNamespace } from "@/shared/api/graphql/generated/graphql";
import useQuery from "@/shared/api/graphql/useQuery";
import { constructPath } from "@/shared/api/rest/fetch";
import { LinkButton } from "@/shared/components/buttons/button-primitive";
import { Col, Row } from "@/shared/components/container";
import { Skeleton } from "@/shared/components/skeleton";
import {
  Combobox,
  ComboboxContent,
  ComboboxItem,
  ComboboxList,
} from "@/shared/components/ui/combobox";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { focusVisibleStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";
import { useSetAtom } from "jotai";
import { ChevronsUpDownIcon } from "lucide-react";
import { useEffect, useId } from "react";
import { useNavigate, useParams } from "react-router";
import { StringParam, useQueryParam } from "use-query-params";
import { defaultIpNamespaceAtom } from "./common/namespace.state";
import { constructPathForIpam } from "./common/utils";
import { IPAM_QSP, IPAM_ROUTE, IPAM_TABS, NAMESPACE_GENERIC } from "./constants";

interface IpNamespaceSelectorProps {
  className?: string;
}

export default function IpNamespaceSelector({ ...props }: IpNamespaceSelectorProps) {
  const { loading, data, error } = useQuery(GET_IP_NAMESPACES);

  if (loading) {
    return <Skeleton className="h-10 w-80" />;
  }

  if (error) {
    return null;
  }

  const namespaces = data?.[NAMESPACE_GENERIC]?.edges.map((edge: any) => edge.node) ?? [];

  return <IpNamespaceSelectorContent namespaces={namespaces} {...props} />;
}

interface IpNamespaceSelectorContentProps extends IpNamespaceSelectorProps {
  namespaces: Array<IpamNamespace>;
}

const IpNamespaceSelectorContent = ({ namespaces, className }: IpNamespaceSelectorContentProps) => {
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
    <div className={classNames("flex gap-2 items-center", className)}>
      <Combobox>
        <PopoverTrigger
          id={id}
          data-testid="namespace-select"
          className={classNames(
            focusVisibleStyle,
            "flex flex-col w-full rounded-md p-1 m-1",
            "border border-transparent",
            "hover:bg-gray-100"
          )}
        >
          <Row className="text-xs text-gray-600">IP Namespace</Row>
          <Row className="text-sm">
            {currentNamespace ? getNodeLabel(currentNamespace as any) : null}

            <ChevronsUpDownIcon className="ml-auto text-gray-600 size-3.5" />
          </Row>
        </PopoverTrigger>

        <ComboboxContent align="start">
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
